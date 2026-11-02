#!/usr/bin/env python3
"""
make_report.py - Membangun laporan PDF dari hasil pengukuran nyata.

Masukan : results/results.csv, results/sysinfo.txt, results/test_output.txt,
          src/*.c (untuk hitung LOC), bin/conv (untuk gambar contoh)
Keluaran: report/Laporan_UTS_Paralel.pdf  (+ report/fig_*.png)

Semua angka dalam laporan dihitung dari CSV; narasi analisis menyesuaikan
dengan data (mis. jumlah core mesin uji). Jalankan ulang di mesin multi-core
Anda:   make bench && make report NIM=... NAMA="..."
"""
import argparse, csv, os, subprocess, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle, Image, Preformatted, KeepTogether, PageBreak)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

ap = argparse.ArgumentParser()
ap.add_argument("--nim", default="")
ap.add_argument("--nama", default="")
ap.add_argument("--out", default=P("report", "Laporan_UTS_Paralel.pdf"))
args = ap.parse_args()
NIM = args.nim or "[NIM]"
NAMA = args.nama or "[Nama]"

# ----------------------------------------------------------------- data
rows = []
with open(P("results", "results.csv")) as fh:
    for r in csv.DictReader(fh):
        rows.append(dict(size=int(r["size"]), filter=r["filter"], border=r["border"], mode=r["mode"],
                         threads=int(r["threads"]), read=float(r["read_ms"]), cmed=float(r["compute_ms"]),
                         cmin=float(r["compute_min_ms"]), write=float(r["write_ms"]), ok=int(r["correct"])))
sysinfo = {}
with open(P("results", "sysinfo.txt")) as fh:
    for line in fh:
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            sysinfo[k] = v
CORES = int(sysinfo.get("nproc", "1"))
REPEATS = sysinfo.get("repeats", "?")
SIZE = rows[0]["size"]
THREADS = sorted({r["threads"] for r in rows if r["mode"] != "serial"})
MAXP = max(THREADS)
FILTERS = ["gaussian", "sobel"]
FNAME = {"gaussian": "Gaussian 5x5", "sobel": "Sobel 3x3"}

def get(filt, border, mode, p=1, size=SIZE):
    for r in rows:
        if (r["size"], r["filter"], r["border"], r["mode"], r["threads"]) == (size, filt, border, mode, 1 if mode == "serial" else p):
            return r
    raise KeyError((filt, border, mode, p))

def total(r):  # waktu end-to-end: baca + komputasi terbaik + tulis
    return r["read"] + r["cmin"] + r["write"]

def speedup(filt, mode, p, border="replicate"):
    return get(filt, border, "serial")["cmin"] / get(filt, border, mode, p)["cmin"]

def count_loc(path):
    """(baris total, baris kode) - kode = bukan kosong & bukan komentar."""
    total_l = code = 0
    in_block = False
    with open(path) as fh:
        for line in fh:
            total_l += 1
            s = line.strip()
            if in_block:
                if "*/" in s:
                    in_block = False
                continue
            if not s or s.startswith("//"):
                continue
            if s.startswith("/*"):
                if "*/" not in s:
                    in_block = True
                continue
            code += 1
    return total_l, code

# ----------------------------------------------------------------- gambar
def fig_path(n): return P("report", n)

def read_pgm(path):
    with open(path, "rb") as fh:
        data = fh.read()
    toks, i = [], 2
    while len(toks) < 3:
        while data[i:i+1].isspace(): i += 1
        j = i
        while not data[j:j+1].isspace(): j += 1
        toks.append(int(data[i:j])); i = j
    i += 1
    w, h, _ = toks
    return w, h, data[i:i + w * h]

def make_figures():
    colr = {"pthreads": "#1f77b4", "openmp": "#d62728"}
    mark = {"pthreads": "o", "openmp": "s"}
    lab = {"pthreads": "Pthreads", "openmp": "OpenMP"}
    for kind, fname in (("speedup", "fig_speedup.png"), ("eff", "fig_eff.png")):
        fig, axs = plt.subplots(1, 2, figsize=(8.2, 3.2))
        for ax, f in zip(axs, FILTERS):
            if kind == "speedup":
                ax.plot([1, MAXP], [1, MAXP], "k--", lw=1, label="Ideal linear")
                ax.plot(THREADS, [min(p, CORES) for p in THREADS], ":", color="gray", lw=1.4,
                        label=f"Batas hardware ({CORES} core)")
            else:
                ax.axhline(1.0, color="k", ls="--", lw=1, label="Ideal (1.0)")
            for m in ("pthreads", "openmp"):
                ys = [speedup(f, m, p) / (p if kind == "eff" else 1) for p in THREADS]
                ax.plot(THREADS, ys, marker=mark[m], color=colr[m], label=lab[m])
            ax.set_xticks(THREADS); ax.set_xlabel("Jumlah thread (p)")
            ax.set_ylabel("Speedup  S(p)" if kind == "speedup" else "Efficiency  E(p) = S(p)/p")
            ax.set_title(FNAME[f], fontsize=10); ax.grid(alpha=.3)
            if kind == "eff": ax.set_ylim(0, 1.15)
        axs[0].legend(fontsize=7)
        fig.tight_layout(); fig.savefig(fig_path(fname), dpi=170); plt.close(fig)

    # I/O vs compute (serial)
    fig, ax = plt.subplots(figsize=(5.4, 2.6))
    labels, rd, cp, wr = [], [], [], []
    for f in FILTERS:
        r = get(f, "replicate", "serial")
        labels.append(FNAME[f]); rd.append(r["read"]); cp.append(r["cmin"]); wr.append(r["write"])
    ax.barh(labels, rd, color="#ff7f0e", label="Baca PGM")
    ax.barh(labels, cp, left=rd, color="#2ca02c", label="Komputasi")
    ax.barh(labels, wr, left=[a + b for a, b in zip(rd, cp)], color="#9467bd", label="Tulis PGM")
    ax.set_xlabel("Waktu (ms), versi serial"); ax.legend(fontsize=7, loc="lower right"); ax.grid(alpha=.3, axis="x")
    fig.tight_layout(); fig.savefig(fig_path("fig_io.png"), dpi=170); plt.close(fig)

    # contoh citra (potongan 400x400 dari tengah)
    exe, inp = P("bin", "conv"), P("data", f"input_{SIZE}.pgm")
    tmp = {}
    for f in FILTERS:
        outp = P("out", f"fig_{f}.pgm")
        subprocess.run([exe, "-i", inp, "-o", outp, "-m", "openmp", "-t", "4", "-f", f, "-b", "replicate", "-r", "1"],
                       check=True, stdout=subprocess.DEVNULL)
        tmp[f] = read_pgm(outp)
    tmp["input"] = read_pgm(inp)
    import numpy as np
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.6))
    for ax, (key, title) in zip(axs, (("input", "Input"), ("gaussian", "Gaussian 5x5"), ("sobel", "Sobel"))):
        w, h, d = tmp[key]
        a = np.frombuffer(d, dtype=np.uint8).reshape(h, w)
        c = a[h // 2 - 200:h // 2 + 200, w // 2 - 200:w // 2 + 200]
        ax.imshow(c, cmap="gray", vmin=0, vmax=255); ax.set_title(title, fontsize=9); ax.axis("off")
    fig.tight_layout(); fig.savefig(fig_path("fig_sample.png"), dpi=170); plt.close(fig)

make_figures()

# ----------------------------------------------------------------- gaya
pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DV-B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DV-I", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DV-BI", "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"))
pdfmetrics.registerFont(TTFont("DVM", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

body = ParagraphStyle("body", fontName="DV", fontSize=9.2, leading=13.2, alignment=TA_JUSTIFY, spaceAfter=5)
h1 = ParagraphStyle("h1", fontName="DV-B", fontSize=13, leading=16, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#14325c"))
h2 = ParagraphStyle("h2", fontName="DV-B", fontSize=10.3, leading=13, spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#14325c"))
cap = ParagraphStyle("cap", parent=body, fontSize=8, leading=10.5, alignment=TA_CENTER, textColor=colors.HexColor("#444444"), spaceAfter=8)
code = ParagraphStyle("code", fontName="DVM", fontSize=7.4, leading=9.4)
cell = ParagraphStyle("cell", fontName="DV", fontSize=8, leading=10)
cellb = ParagraphStyle("cellb", parent=cell, fontName="DV-B")
bul = ParagraphStyle("bul", parent=body, leftIndent=14, bulletIndent=3, spaceAfter=2)
title = ParagraphStyle("title", fontName="DV-B", fontSize=15, leading=19, alignment=TA_CENTER, textColor=colors.HexColor("#14325c"))
sub = ParagraphStyle("sub", fontName="DV", fontSize=10, leading=14, alignment=TA_CENTER)

def Pp(t): return Paragraph(t, body)
def H1(t): return Paragraph(t, h1)
def H2(t): return Paragraph(t, h2)
def B(items): return [Paragraph(i, bul, bulletText="•") for i in items]
def Code(t): return KeepTogether([Preformatted(t.strip("\n"), code, dedent=0)])

def Tbl(data, widths, header=1, align_right_from=None, zebra=True, fs=8):
    st = ParagraphStyle("c", parent=cell, fontSize=fs, leading=fs + 2)
    stb = ParagraphStyle("cb", parent=st, fontName="DV-B")
    d = []
    for i, row in enumerate(data):
        d.append([Paragraph(str(c), stb if i < header else st) if isinstance(c, str) else c for c in row])
    t = Table(d, colWidths=widths, repeatRows=header)
    sty = [("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#999999")),
           ("BACKGROUND", (0, 0), (-1, header - 1), colors.HexColor("#dfe8f5")),
           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if zebra:
        for i in range(header, len(d)):
            if (i - header) % 2: sty.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f6f8fb")))
    t.setStyle(TableStyle(sty))
    return t

def Fig(path, width_cm, caption):
    from PIL import Image as PI
    w, h = PI.open(path).size
    img = Image(path, width=width_cm * cm, height=width_cm * cm * h / w)
    return KeepTogether([img, Paragraph(caption, cap)])

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 7.5); canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(2 * cm, 1.2 * cm, f"UTS Komputer Paralel - Konvolusi Citra: Pthreads vs OpenMP | {NIM} - {NAMA}")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Halaman {doc.page}")
    canvas.restoreState()

doc = BaseDocTemplate(args.out, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.9 * cm,
                      title="Laporan UTS Komputer Paralel - Konvolusi Citra", author=f"{NAMA} ({NIM})")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=footer)])
W = doc.width
S = []

# ----------------------------------------------------------------- nilai turunan
f_ = lambda x, n=2: f"{x:.{n}f}"
s_pth = {f: speedup(f, "pthreads", MAXP) for f in FILTERS}
s_omp = {f: speedup(f, "openmp", MAXP) for f in FILTERS}
ser = {f: get(f, "replicate", "serial") for f in FILTERS}
io_frac = {f: (ser[f]["read"] + ser[f]["write"]) / total(ser[f]) for f in FILTERS}
npx = SIZE * SIZE
ns_per_px = {f: ser[f]["cmin"] * 1e6 / npx for f in FILTERS}
mbps = {f: (2 * npx / 1e6) / (ser[f]["cmin"] / 1e3) for f in FILTERS}  # MB/s (baca+tulis 1 byte/piksel)
correct_all = all(r["ok"] == 1 for r in rows)
n_runs = sum(1 for r in rows if r["mode"] != "serial")
n_ok = sum(1 for r in rows if r["mode"] != "serial" and r["ok"] == 1)
noisy = [r for r in rows if r["cmed"] > 1.3 * r["cmin"]]
diffs = []
for f in FILTERS:
    for p in THREADS:
        a, b = get(f, "replicate", "pthreads", p)["cmin"], get(f, "replicate", "openmp", p)["cmin"]
        diffs.append(abs(a - b) / min(a, b) * 100)
mean_diff = sum(diffs) / len(diffs)
ovh = {}
for m in ("pthreads", "openmp"):
    ovh[m] = [(get(f, "replicate", m, MAXP)["cmin"] / get(f, "replicate", "serial")["cmin"] - 1) * 100 for f in FILTERS]

# ----------------------------------------------------------------- halaman judul
S += [Paragraph("LAPORAN UJIAN TENGAH SEMESTER GANJIL TA-2026/2027", title), Spacer(1, 3),
      Paragraph("Komputer Paralel (Sistem Terdistribusi) - Program Studi Teknik Informatika<br/>"
                "Fakultas Teknik dan Ilmu Komputer, Universitas Cendekia Abditama", sub), Spacer(1, 6),
      Paragraph("Konvolusi Citra Paralel (Gaussian Blur 5x5 dan Sobel): Perbandingan POSIX Threads dan OpenMP", title),
      Spacer(1, 5),
      Paragraph(f"{NAMA} - NIM {NIM}<br/>Dosen: Dr. Ir. Antonius Irianto. S, ST., MT &nbsp;|&nbsp; Opsi B &nbsp;|&nbsp; 2 November 2026", sub),
      Spacer(1, 6)]

# ----------------------------------------------------------------- 1. PENDAHULUAN
S += [H1("1. PENDAHULUAN"), H2("1.1 Latar Belakang")]
S.append(Pp(
    f"Konvolusi spasial adalah operasi dasar pengolahan citra: setiap piksel keluaran dihitung dari jumlah berbobot piksel-piksel "
    f"tetangganya. Untuk citra W x H dengan kernel k x k, biaya komputasinya O(W·H·k²). Pada citra {SIZE}x{SIZE} dengan kernel "
    f"Gaussian 5x5, ada {npx/1e6:.0f} juta piksel dan sekitar {npx*25/1e6:.0f} juta operasi perkalian-penjumlahan per pass, sehingga "
    f"masalah ini cukup besar untuk diuntungkan paralelisme. Secara prinsip tiap piksel keluaran independen (data-parallel), tetapi "
    f"implementasi yang benar menuntut perhatian pada tiga hal yang dituntut soal: (1) <b>piksel di area border</b>, yang kernel-nya "
    f"memerlukan tetangga di luar citra; (2) <b>pembagian workload</b> yang membuat sebuah band memerlukan baris milik band tetangga "
    f"(region overlap/halo); dan (3) perbandingan porsi <b>I/O</b> terhadap <b>komputasi</b>, karena bagian I/O bersifat serial dan "
    f"membatasi percepatan menurut Hukum Amdahl."))
S.append(Pp(
    "Dua model pemrograman shared-memory dibandingkan di sini. <b>POSIX Threads (Pthreads)</b> menuntut programmer membuat, "
    "mempartisi pekerjaan, dan menyinkronkan thread secara eksplisit. <b>OpenMP</b> memindahkan sebagian besar pekerjaan itu ke compiler "
    "dan runtime melalui directive. Keduanya dijalankan pada inti komputasi yang identik agar perbedaan yang terukur benar-benar berasal "
    "dari mekanisme paralelisasinya."))
S += [H2("1.2 Tujuan Implementasi")]
S += B([f"Mengimplementasikan filter Gaussian blur 5x5 dan deteksi tepi Sobel pada citra grayscale PGM berukuran minimal 2000x2000 "
        f"(diuji pada {SIZE}x{SIZE}) tanpa library citra, dengan dua strategi border (zero-padding dan replicate).",
        "Membuat tiga versi: serial (baseline), Pthreads, dan OpenMP, serta membuktikan hasil paralel identik byte-per-byte dengan serial.",
        f"Mengukur waktu eksekusi, speedup, dan efficiency untuk 1, 2, 4, dan 8 thread, memisahkan waktu I/O dan komputasi.",
        "Menganalisis secara kritis kompleksitas kode, bottleneck (Hukum Amdahl), anomali, dan trade-off kemudahan vs kontrol."])

# ----------------------------------------------------------------- 2. DESAIN
S += [H1("2. DESAIN IMPLEMENTASI"), H2("2.1 Algoritma Serial (Baseline)")]
S.append(Pp(
    "Program membaca PGM (P5 biner atau P2 ASCII) dengan parser sendiri, menjalankan konvolusi, lalu menulis PGM P5. Satuan kerja "
    "terkecil adalah <font name='DVM'>filter_row(in, out, f, b, y)</font>: menghitung satu baris keluaran. Versi serial hanyalah loop "
    "<font name='DVM'>for y in 0..H-1</font> yang memanggil fungsi tersebut; kedua versi paralel memanggil fungsi yang sama sehingga inti "
    "komputasi tidak berbeda. Seluruh aritmetika memakai integer (Gaussian: bobot [1 4 6 4 1]⊗[1 4 6 4 1] dengan jumlah 256 lalu dibagi 256 dengan "
    "pembulatan; Sobel: Gx dan Gy integer, magnitudo √(Gx²+Gy²) dibulatkan dan di-clamp ke 255), sehingga hasil paralel harus identik dengan serial."))
S.append(Code("""
for y in 0 .. H-1:                       # filter_row(y)
    if y berada di interior vertikal:    # y >= r dan y < H-r
        for x in 0 .. r-1:        out[y][x] = konvolusi_tepi(x, y)    # dengan pengecekan batas
        for x in r .. W-r-1:      out[y][x] = konvolusi_cepat(x, y)   # tanpa pengecekan batas
        for x in W-r .. W-1:      out[y][x] = konvolusi_tepi(x, y)
    else:                                 # baris paling atas/bawah: seluruhnya tepi
        for x in 0 .. W-1:        out[y][x] = konvolusi_tepi(x, y)
"""))
S.append(Spacer(1, 4))
S.append(Pp(
    "<b>Penanganan border.</b> Pada jalur tepi, piksel di luar citra diambil lewat <font name='DVM'>fetch()</font>: untuk "
    "<i>zero-padding</i> nilainya 0, untuk <i>replicate</i> koordinat di-clamp ke piksel tepi terdekat. Jalur cepat untuk piksel interior "
    f"menghindari pengecekan batas pada setiap akses. Untuk Gaussian (r=2) hanya sekitar {(1-(SIZE-4)**2/SIZE**2)*100:.2f}% piksel memakai jalur tepi, "
    "sehingga border tidak menjadi masalah performa, tetapi tetap harus benar. Karena citra disimpan row-major dan kernel menyapu baris "
    "demi baris, akses memori bersifat sekuensial dan ramah cache."))
S.append(Tbl([["File", "Peran"],
              ["src/filter.c / filter.h", "Inti konvolusi, border, versi serial"],
              ["src/par_pthreads.c", "Paralelisasi eksplisit dengan POSIX Threads"],
              ["src/par_openmp.c", "Paralelisasi dengan OpenMP (compiler directive)"],
              ["src/pgm.c, src/main.c", "I/O PGM tanpa library; driver CLI dan pengukur waktu"],
              ["tools/gen_pgm.c, tools/pgmcmp.c", "Pembangkit citra uji (seed tetap 42) dan pembanding byte-per-byte"],
              ["tests/test_correct.c, scripts/bench.sh", "Verifikasi correctness dan benchmark otomatis"]],
             [W * .38, W * .62]))

S += [H2("2.2 Strategi Paralelisasi Pthreads")]
S.append(Pp(
    "<b>Pembagian workload.</b> Domain dipartisi per <i>blok baris kontigu</i> (static). Dengan p thread dan H baris, thread i menerima "
    "⌊H/p⌋ baris ditambah satu baris bila i &lt; H mod p, sehingga selisih beban antar thread paling banyak satu baris. Pemilihan blok baris "
    "(bukan kolom atau tile) menjaga akses memori sekuensial dalam band dan hanya menyisakan dua batas band. Jumlah thread dibatasi "
    "tidak lebih dari H. Thread utama ikut mengerjakan band 0, sehingga hanya p-1 thread yang dibuat."))
S.append(Pp(
    "<b>Region overlap (halo).</b> Piksel di dekat batas band memerlukan baris tetangga dari band lain (r baris di atas/bawah). Karena "
    "citra masukan <i>read-only</i> selama komputasi dan tersimpan di memori bersama, setiap thread cukup membaca baris halo langsung dari "
    "citra masukan; tidak perlu menyalin region overlap. Ini pembeda penting dengan model memori terdistribusi (MPI), yang akan memerlukan "
    "pertukaran halo."))
S.append(Pp(
    "<b>Mekanisme sinkronisasi.</b> Tidak ada mutex: tiap thread menulis baris keluaran yang saling lepas sehingga tidak ada write-write conflict "
    "maupun race condition, dan masukan hanya dibaca. Satu-satunya sinkronisasi adalah <font name='DVM'>pthread_join</font> sebagai barrier di akhir. "
    "Bila <font name='DVM'>pthread_create</font> gagal, program menjalankan fallback serial agar hasil tetap benar."))
S.append(Code("""
Task tk[i] = { in, out, f, b, y0, y1 };           // partisi: y1-y0 = H/p (+1 bila i < H%p)
for (i = 1; i < p; i++) pthread_create(&th[i], NULL, worker, &tk[i]);
worker(&tk[0]);                                    // thread utama = band 0
for (i = 1; i < p; i++) pthread_join(th[i], NULL); // barrier
"""))

S += [H2("2.3 Strategi Paralelisasi OpenMP")]
S.append(Pp(
    "<b>Pemilihan pragma dan clause.</b> Seluruh paralelisasi hanya satu directive pada loop baris terluar:"))
S.append(Code("""
#pragma omp parallel for num_threads(nthreads) schedule(static) \\
            default(none) shared(in, out, f, b, h)
for (int y = 0; y < h; y++)
    filter_row(in, out, f, b, y);
"""))
S.append(Spacer(1, 3))
S.append(Tbl([["Elemen", "Pilihan", "Alasan"],
              ["parallel for", "loop baris (terluar)", "Iterasi independen; granularitas besar (satu baris = ribuan piksel) sehingga overhead runtime kecil"],
              ["schedule(static)", "blok kontigu", "Beban tiap baris seragam; lokalitas cache terbaik; setara dengan partisi manual Pthreads"],
              ["num_threads(p)", "p dari CLI", "Memudahkan sweep 1, 2, 4, 8 tanpa mengubah OMP_NUM_THREADS"],
              ["default(none)", "scope eksplisit", "Memaksa setiap variabel dideklarasikan, mencegah variabel shared tidak sengaja"]],
             [W * .2, W * .2, W * .6]))
S.append(Spacer(1, 4))
S.append(Tbl([["Variabel", "Scope", "Alasan"],
              ["in", "shared", "Citra masukan read-only; semua thread membaca (termasuk baris halo)"],
              ["out", "shared", "Ditulis pada baris yang berbeda per iterasi, tidak ada konflik"],
              ["f, b, h", "shared", "Konstanta selama region (jenis filter, border, tinggi)"],
              ["y", "private", "Variabel loop; otomatis private pada worksharing loop"]],
             [W * .2, W * .15, W * .65]))
S.append(Spacer(1, 4))
S.append(Pp(
    "Tidak diperlukan clause <font name='DVM'>reduction</font> karena tidak ada akumulator bersama. Barrier implisit di akhir "
    "<font name='DVM'>parallel for</font> menggantikan <font name='DVM'>pthread_join</font>. Border dan halo ditangani dengan cara yang sama seperti "
    "Pthreads: baris halo dibaca langsung dari <font name='DVM'>in</font>."))

# ----------------------------------------------------------------- 3. HASIL
S += [H1("3. HASIL PENGUJIAN"), H2("3.1 Lingkungan dan Metodologi")]
S.append(Tbl([["Item", "Nilai"],
              ["CPU", sysinfo.get("cpu", "?")],
              ["Core logis tersedia (nproc)", str(CORES)],
              ["Compiler / OS", f"{sysinfo.get('gcc','?')} / {sysinfo.get('kernel','?')}"],
              ["Flag kompilasi", "gcc -O2 -Wall -Wextra -std=gnu11 -fopenmp (tanpa -ffast-math)"],
              ["Data uji", f"PGM sintetis {SIZE}x{SIZE} ({npx/1e6:.0f} juta piksel, seed 42): gradien, lingkaran, persegi, noise"],
              ["Pengukuran", f"1x warm-up lalu {REPEATS} repetisi; dilaporkan <b>waktu terbaik (min)</b> dan median; waktu baca/tulis diukur terpisah"],
              ["Variasi", "thread 1, 2, 4, 8 (Pthreads dan OpenMP); filter Gaussian dan Sobel; border replicate dan zero"]],
             [W * .27, W * .73]))
S.append(Spacer(1, 3))
S.append(Pp(
    "Speedup dan efficiency dihitung dari waktu komputasi terbaik: S(p) = T<sub>serial</sub> / T<sub>p</sub> dan E(p) = S(p)/p. Waktu terbaik dipilih "
    "karena lebih tahan terhadap gangguan sesaat dari sistem (scheduler, proses lain) pada benchmark CPU-bound; median tetap ditampilkan pada tabel. "
    "Catatan: file masukan sudah berada di page cache OS pada saat dibaca, sehingga waktu baca di sini lebih kecil daripada pembacaan dari disk dingin."))

S += [H2("3.2 Verifikasi Correctness")]
tests_line = ""
try:
    tl = [l.strip() for l in open(P("results", "test_output.txt")) if l.startswith("HASIL")]
    tests_line = tl[-1] if tl else ""
except OSError:
    pass
S.append(Pp(
    "Correctness diverifikasi dengan tiga lapis. <b>(1) Tes manual</b> pada citra konstan 5x5 bernilai 100 yang hasilnya dapat dihitung dengan tangan: "
    "Gaussian+replicate harus tetap 100 di semua piksel; Gaussian+zero pada sudut (0,0) hanya memiliki bobot 1D 6+4+1 = 11 sehingga "
    "(11·11·100+128)>>8 = 47; Sobel+replicate harus 0 (tidak ada tepi); Sobel+zero pada sudut menghasilkan Gx=Gy=300 sehingga magnitudo 424 di-clamp ke 255. "
    "<b>(2) Tes acak</b> membandingkan serial, Pthreads, dan OpenMP dengan implementasi referensi naif yang independen, pada enam ukuran citra "
    "(termasuk 1x7, 2x2, 5x5 yang lebih kecil dari kernel, dan 37x53 yang tidak habis dibagi jumlah thread), kedua filter, kedua border, dan 1 sampai 16 thread. "
    f"Hasil: <b>{tests_line.replace('HASIL: ', '') or 'lihat results/test_output.txt'}</b>. "
    f"<b>(3) Perbandingan byte-per-byte</b> pada citra {SIZE}x{SIZE}: seluruh {n_ok} dari {n_runs} konfigurasi paralel pada benchmark "
    f"({'identik' if n_ok == n_runs else 'TIDAK semuanya identik'} dengan keluaran serial menurut <font name='DVM'>pgmcmp</font>)."))
S.append(Fig(fig_path("fig_sample.png"), 13.5, "Gambar 1. Potongan 400x400 dari tengah citra: masukan, hasil Gaussian 5x5, dan hasil Sobel (replicate)."))

S += [H2("3.3 Tabel Waktu Eksekusi")]
S.append(Pp(f"Tabel 1 dan 2 memuat waktu (ms) untuk border <i>replicate</i>. Kolom Total = baca + komputasi (min) + tulis. Speedup dihitung terhadap komputasi serial."))
def time_table(f):
    hdr = ["Mode", "p", "Baca", "Komp. median", "Komp. min", "Tulis", "Total", "Speedup", "Efficiency"]
    data = [hdr]
    r = get(f, "replicate", "serial")
    data.append(["Serial", "1", f_(r["read"]), f_(r["cmed"]), f_(r["cmin"]), f_(r["write"]), f_(total(r)), "1.00", "1.00"])
    for m, nm in (("pthreads", "Pthreads"), ("openmp", "OpenMP")):
        for p in THREADS:
            r = get(f, "replicate", m, p)
            sp = speedup(f, m, p)
            data.append([nm, str(p), f_(r["read"]), f_(r["cmed"]), f_(r["cmin"]), f_(r["write"]), f_(total(r)), f_(sp), f_(sp / p)])
    return Tbl(data, [W * x for x in (.13, .06, .09, .15, .13, .09, .10, .12, .13)], fs=7.6)
S.append(Paragraph("<b>Tabel 1.</b> Gaussian 5x5, border replicate (ms)", body)); S.append(time_table("gaussian")); S.append(Spacer(1, 6))
S.append(Paragraph("<b>Tabel 2.</b> Sobel 3x3, border replicate (ms)", body)); S.append(time_table("sobel")); S.append(Spacer(1, 6))
zr = []
for f in FILTERS:
    a, z = get(f, "replicate", "serial"), get(f, "zero", "serial")
    zr.append([FNAME[f], f_(a["cmin"]), f_(z["cmin"]), f_((z["cmin"] / a["cmin"] - 1) * 100, 1) + " %"])
S.append(Paragraph("<b>Tabel 3.</b> Pengaruh strategi border pada komputasi serial (ms, min)", body))
S.append(Tbl([["Filter", "Replicate", "Zero-padding", "Selisih"]] + zr, [W * .3, W * .23, W * .25, W * .22]))
S.append(Pp("Selisih antara dua strategi border sangat kecil karena hanya piksel di tepi yang berbeda jalurnya; strategi border mempengaruhi <i>nilai</i> piksel tepi "
            "(mis. Sobel+zero menghasilkan garis tepi palsu di pinggir citra), bukan performa."))

S += [H2("3.4 Grafik Speedup dan Efficiency")]
S.append(Fig(fig_path("fig_speedup.png"), 15.5, "Gambar 2. Speedup waktu komputasi terhadap jumlah thread (border replicate). Garis titik abu-abu = batas hardware min(p, core)."))
S.append(Fig(fig_path("fig_eff.png"), 15.5, "Gambar 3. Efficiency E(p) = S(p)/p."))
S.append(Pp(
    f"Pada {MAXP} thread, speedup komputasi Gaussian adalah <b>{f_(s_pth['gaussian'])}x</b> (Pthreads) dan <b>{f_(s_omp['gaussian'])}x</b> (OpenMP); "
    f"untuk Sobel <b>{f_(s_pth['sobel'])}x</b> dan <b>{f_(s_omp['sobel'])}x</b>. Mesin uji memiliki <b>{CORES}</b> core logis, sehingga batas atas speedup adalah min({MAXP}, {CORES}) = {min(MAXP, CORES)}x. "
    f"Selisih rata-rata waktu komputasi antara Pthreads dan OpenMP pada semua titik uji adalah {mean_diff:.1f}%."))

S += [H2("3.5 Analisis I/O-bound vs Compute-bound")]
S.append(Fig(fig_path("fig_io.png"), 10.5, "Gambar 4. Dekomposisi waktu eksekusi serial: baca, komputasi, tulis."))
S.append(Pp(
    f"Pada versi serial, I/O (baca + tulis) hanya {io_frac['gaussian']*100:.1f}% dari total untuk Gaussian dan {io_frac['sobel']*100:.1f}% untuk Sobel. "
    f"Waktu komputasi sekitar {ns_per_px['gaussian']:.1f} ns/piksel (Gaussian) dan {ns_per_px['sobel']:.1f} ns/piksel (Sobel), sedangkan trafik data efektif hanya "
    f"sekitar {mbps['gaussian']:.0f} MB/s - jauh di bawah bandwidth memori mesin modern (orde puluhan GB/s). Artinya inti konvolusi bersifat <b>compute-bound</b>: "
    "tiap byte yang dibaca dipakai kembali oleh 25 (Gaussian) atau 9 (Sobel) operasi kali-tambah dari cache, sehingga menambah core akan meningkatkan throughput, "
    "bukan membentur dinding bandwidth. Sebaliknya, <b>end-to-end</b> program menjadi lebih dekat ke I/O-bound seiring bertambahnya thread, karena bagian I/O tetap serial "
    "(dibahas pada 4.2)."))

# ----------------------------------------------------------------- 4. ANALISIS KRITIS
S += [H1("4. ANALISIS KRITIS")]
S += [H2("4.1 Perbandingan Kompleksitas Kode (LOC dan Maintenance)")]
loc = {n: count_loc(P("src", n)) for n in ("filter.c", "par_pthreads.c", "par_openmp.c", "pgm.c", "main.c")}
lp, lo = loc["par_pthreads.c"], loc["par_openmp.c"]
S.append(Tbl([["File", "Baris total", "LOC kode (tanpa komentar/kosong)"],
              ["filter.c (inti + serial, dipakai bersama)", str(loc["filter.c"][0]), str(loc["filter.c"][1])],
              ["par_pthreads.c", str(lp[0]), str(lp[1])],
              ["par_openmp.c", str(lo[0]), str(lo[1])],
              ["pgm.c", str(loc["pgm.c"][0]), str(loc["pgm.c"][1])],
              ["main.c", str(loc["main.c"][0]), str(loc["main.c"][1])]],
             [W * .5, W * .2, W * .3]))
S.append(Paragraph("Tabel 4. Ukuran kode (dihitung otomatis oleh make_report.py)", cap))
S.append(Pp(
    f"Lapisan paralel Pthreads membutuhkan <b>{lp[1]} LOC</b> kode, sedangkan OpenMP <b>{lo[1]} LOC</b> (rasio {lp[1]/max(lo[1],1):.1f}x), padahal inti komputasinya sama. "
    "Selisih itu bukan sekadar jumlah baris, melainkan <i>tanggung jawab</i> yang dipindahkan ke programmer: mendefinisikan struct argumen, fungsi worker dengan "
    "signature <font name='DVM'>void*(void*)</font>, menghitung partisi dengan penanganan sisa (H mod p), alokasi array thread/task, memeriksa kegagalan "
    "<font name='DVM'>pthread_create</font>, dan join. Setiap bagian itu adalah tempat potensi bug (off-by-one pada band, kebocoran memori, lupa join). "
    "Pada OpenMP, satu pragma menggantikan seluruhnya dan versi serial tetap valid bila compiler tidak mendukung OpenMP (pragma diabaikan), sehingga "
    "<i>incremental parallelization</i> aman. Dari sisi maintenance, perubahan kebijakan penjadwalan di OpenMP cukup mengganti clause "
    "(<font name='DVM'>schedule(dynamic, 16)</font>), sedangkan di Pthreads harus menulis ulang partisi atau menambah antrean tugas dengan mutex/atomic."))

S += [H2("4.2 Analisis Bottleneck dan Hukum Amdahl")]
S.append(Pp(
    "Hukum Amdahl: S(p) = 1 / (f + (1-f)/p), dengan f fraksi serial. Pada program ini bagian serialnya adalah baca PGM, alokasi, dan tulis PGM; "
    f"inti konvolusi paralel. Dari pengukuran serial: f = {io_frac['gaussian']:.3f} (Gaussian) dan f = {io_frac['sobel']:.3f} (Sobel). "
    f"Batas Amdahl pada p→∞ adalah 1/f = {1/io_frac['gaussian']:.1f}x untuk Gaussian dan {1/io_frac['sobel']:.1f}x untuk Sobel - artinya semakin ringan komputasinya "
    "(Sobel), semakin cepat I/O menjadi pembatas. Tabel 5 membandingkan batas Amdahl dengan speedup end-to-end terukur."))
def amdahl_rows(f):
    fr = io_frac[f]; sr = total(get(f, "replicate", "serial")); out = []
    for p in THREADS:
        am = 1 / (fr + (1 - fr) / p)
        pt = sr / total(get(f, "replicate", "pthreads", p)); om = sr / total(get(f, "replicate", "openmp", p))
        out.append([FNAME[f], str(p), f_(min(p, CORES)), f_(am), f_(pt), f_(om)])
    return out
S.append(Tbl([["Filter", "p", "Batas hardware min(p,core)", "Amdahl (f dari serial)", "Terukur Pthreads", "Terukur OpenMP"]]
             + amdahl_rows("gaussian") + amdahl_rows("sobel"), [W * .17, W * .07, W * .24, W * .2, W * .16, W * .16], fs=7.6))
S.append(Paragraph("Tabel 5. Speedup end-to-end (baca+komputasi+tulis) vs batas Amdahl. Amdahl dihitung mengasumsikan p core tersedia.", cap))
S.append(Pp(
    "Selain Amdahl, <b>Karp-Flatt metric</b> e = (1/S - 1/p) / (1 - 1/p) mengukur fraksi serial <i>efektif</i> dari data terukur. "
    "Nilai e yang bertambah seiring p menandakan overhead paralel (pembuatan thread, kontensi memori, ketidakseimbangan beban) dan bukan sekadar bagian serial tetap."))
kf = []
for f in FILTERS:
    for m, nm in (("pthreads", "Pthreads"), ("openmp", "OpenMP")):
        vals = []
        for p in THREADS:
            if p == 1: continue
            s = speedup(f, m, p)
            vals.append(f_((1 / s - 1 / p) / (1 - 1 / p), 3))
        kf.append([FNAME[f], nm] + vals)
S.append(Tbl([["Filter", "Mode"] + [f"e (p={p})" for p in THREADS if p != 1]] + kf, [W * .22, W * .18] + [W * .2] * (len(THREADS) - 1)))
S.append(Paragraph("Tabel 6. Karp-Flatt metric dari speedup komputasi.", cap))

S += [H2("4.3 Pembahasan Anomali")]
if CORES < MAXP:
    S.append(Pp(
        f"<b>Anomali utama: speedup tidak mengikuti garis ideal.</b> Mesin uji hanya menyediakan {CORES} core logis, sehingga thread melebihi {CORES} tidak dapat berjalan "
        f"serentak; mereka hanya di-time-slice oleh scheduler OS. Batas speedup nyata adalah min(p, {CORES}) = {min(MAXP, CORES)}x, dan hasil terukur "
        f"({f_(s_pth['gaussian'])}x - {f_(s_omp['gaussian'])}x pada {MAXP} thread untuk Gaussian) konsisten dengan batas itu. Ini <b>bukan</b> cacat implementasi: "
        f"data justru menunjukkan <i>overhead</i> paralelisme sangat kecil, yaitu perubahan waktu komputasi pada {MAXP} thread dibanding serial hanya "
        f"{ovh['pthreads'][0]:+.1f}% / {ovh['pthreads'][1]:+.1f}% (Pthreads, Gaussian/Sobel) dan {ovh['openmp'][0]:+.1f}% / {ovh['openmp'][1]:+.1f}% (OpenMP). "
        f"Kurva speedup yang bermakna hanya dapat diperoleh pada mesin dengan ≥{MAXP} core fisik (jalankan <font name='DVM'>make bench && make report</font> di mesin tersebut)."))
else:
    low = [(f, m, p) for f in FILTERS for m in ("pthreads", "openmp") for p in THREADS if p > 1 and speedup(f, m, p) / p < 0.7]
    if low:
        S.append(Pp(
            f"<b>Efficiency di bawah 70%</b> teramati pada {len(low)} titik uji (contoh: {FNAME[low[0][0]]}, {low[0][1]}, p={low[0][2]}, "
            f"E = {f_(speedup(*low[0]) / low[0][2])}). Penyebab yang paling mungkin, yang dapat diverifikasi lebih lanjut dengan perf/likwid: (a) core logis "
            "yang sebenarnya hyper-thread sehingga berbagi unit eksekusi; (b) persaingan bandwidth cache L3/memori; (c) penurunan frekuensi turbo saat banyak core aktif; "
            "(d) overhead pembuatan thread pada beban kecil. Karena Karp-Flatt (Tabel 6) menunjukkan tren e terhadap p, kenaikan e mengindikasikan overhead, bukan bagian serial tetap."))
    else:
        S.append(Pp("Seluruh titik uji mencapai efficiency ≥ 70%, sehingga tidak ada anomali skala yang signifikan; inti konvolusi yang compute-bound dan akses memori sekuensial "
                    "berskala baik pada jumlah thread yang diuji."))
if noisy:
    ex = max(noisy, key=lambda r: r["cmed"] / r["cmin"])
    S.append(Pp(
        f"<b>Anomali kedua: noise pengukuran.</b> {len(noisy)} dari {len(rows)} konfigurasi memiliki median lebih dari 30% di atas waktu terbaik "
        f"(terburuk: {FNAME[ex['filter']]}, border {ex['border']}, {ex['mode']}, p={ex['threads']}: median {f_(ex['cmed'])} ms vs min {f_(ex['cmin'])} ms). "
        "Pola seperti ini khas lingkungan yang berbagi CPU (VM/container, proses lain, scheduler). Itulah alasan laporan memakai waktu terbaik dari beberapa repetisi "
        "untuk speedup, dan menampilkan median sebagai pembanding. Untuk klaim yang lebih kuat sebaiknya dilaporkan simpangan baku dari banyak repetisi pada mesin yang idle."))
S.append(Pp(
    f"<b>Anomali ketiga (non-masalah): Pthreads vs OpenMP.</b> Selisih rata-rata waktu komputasi hanya {mean_diff:.1f}%. Karena keduanya memanggil "
    "<font name='DVM'>filter_row</font> yang sama dengan partisi blok-baris yang setara, perbedaan kinerja yang berarti memang tidak diharapkan; yang "
    "membedakan keduanya adalah biaya <i>pengelolaan</i> thread dan kemampuan menyetel penjadwalan, bukan kecepatan inti komputasi."))

S += [H2("4.4 Trade-off antara Kemudahan vs Kontrol")]
S.append(Tbl([["Aspek", "Pthreads", "OpenMP"],
              ["Kemudahan menulis", f"Rendah: {lp[1]} LOC, banyak boilerplate", f"Tinggi: {lo[1]} LOC, satu pragma"],
              ["Kontrol partisi/penjadwalan", "Penuh: pola partisi, antrean tugas, afinitas, prioritas dapat dibuat sendiri", "Terbatas pada schedule(static/dynamic/guided), collapse, proc_bind"],
              ["Sinkronisasi", "Manual: mutex, condvar, barrier, atomic", "Directive: barrier, critical, atomic, reduction"],
              ["Penanganan error", "Eksplisit (kegagalan pthread_create dapat ditangani)", "Hampir tidak ada; gagal dibuat thread ditangani runtime"],
              ["Risiko bug", "Lebih tinggi (partisi, memori, join), data race tetap mungkin di keduanya", "Lebih rendah, namun scope salah (shared/private) menghasilkan race yang sulit dilacak"],
              ["Portabilitas", "POSIX (Linux/macOS); Windows perlu lapisan kompatibilitas", "Lintas platform bila compiler mendukung OpenMP"],
              ["Pemeliharaan", "Kode paralel terjalin dengan logika aplikasi", "Kode serial tetap terbaca; paralelisasi bersifat anotasi"],
              ["Cocok untuk", "Pipeline/producer-consumer, thread berumur panjang, kontrol real-time", "Loop data-parallel numerik seperti konvolusi ini"]],
             [W * .2, W * .4, W * .4], fs=7.6))
S.append(Spacer(1, 4))
S.append(Pp(
    "Kelemahan kedua pendekatan yang perlu dicatat: (1) false sharing pada baris keluaran di batas band dapat terjadi, tetapi dampaknya diabaikan di sini karena "
    f"hanya p-1 batas dibanding {SIZE} baris; (2) partisi statis bergantung pada asumsi beban per baris seragam - benar untuk konvolusi, tetapi tidak untuk filter adaptif, "
    "yang memerlukan dynamic scheduling atau antrean tugas; (3) penghitungan <i>waktu paralel</i> hanya mencakup region komputasi, sehingga manfaat nyata bagi pengguna dibatasi oleh Hukum Amdahl (Bagian 4.2)."))
S.append(Pp(
    "<b>Keterbatasan pengujian.</b> Hasil berasal dari satu mesin/lingkungan; citra masukan sintetis dan berada di page cache OS; satu ukuran citra; "
    "simpangan baku tidak dilaporkan. Optimasi lanjutan yang tidak diimplementasikan: Gaussian separable (dua pass 1D, 10 vs 25 perkalian per piksel), "
    "vektorisasi SIMD eksplisit, dan tiling untuk cache."))

# ----------------------------------------------------------------- 5. KESIMPULAN
S += [H1("5. KESIMPULAN"), H2("5.1 Rekomendasi Penggunaan Pthreads vs OpenMP")]
S += B([f"<b>Gunakan OpenMP</b> untuk loop data-parallel seperti konvolusi: {lo[1]} LOC vs {lp[1]} LOC, kode serial tetap utuh, dan kinerjanya setara (selisih rata-rata {mean_diff:.1f}% pada pengukuran ini).",
        "<b>Gunakan Pthreads</b> bila memerlukan kontrol yang tidak dapat diekspresikan dengan directive: thread berumur panjang, pipeline baca-proses-tulis (untuk menumpuk I/O dengan komputasi), "
        "antrean tugas kustom, afinitas/prioritas, atau penanganan kegagalan pembuatan thread.",
        f"Dalam program ini, peningkatan end-to-end berikutnya paling efektif datang dari <b>mengurangi bagian serial I/O</b> (f = {io_frac['gaussian']:.3f}-{io_frac['sobel']:.3f}) "
        "dan memperkecil biaya per piksel (Gaussian separable, SIMD), bukan dari menambah thread semata."])
S += [H2("5.2 Pembelajaran yang Didapat")]
S += B(["Menghilangkan dependency antar-piksel di border tidak memerlukan sinkronisasi pada shared memory bila masukan read-only dan keluaran dipartisi tanpa tumpang tindih; "
        "kesalahan border lebih mungkin muncul pada logika indeks, itulah sebabnya tes dibuat pada citra yang lebih kecil dari kernel dan ukuran yang tidak habis dibagi jumlah thread.",
        "Jumlah thread tidak boleh melebihi core fisik jika tujuannya speedup: pengukuran harus selalu dibaca bersama spesifikasi mesin (batas min(p, core)).",
        "Tanpa memisahkan waktu I/O dan komputasi, hasil end-to-end akan menyesatkan; Hukum Amdahl terlihat langsung pada data.",
        "Metodologi benchmark penting: warm-up, banyak repetisi, waktu terbaik vs median, dan verifikasi correctness otomatis pada setiap konfigurasi."])

# ----------------------------------------------------------------- 6. DAFTAR PUSTAKA
S += [H1("6. DAFTAR PUSTAKA")]
refs = [
    "Amdahl, G. M. (1967). Validity of the single processor approach to achieving large scale computing capabilities. <i>AFIPS Conference Proceedings</i> (Spring Joint Computer Conference), 30, 483-485.",
    "Butenhof, D. R. (1997). <i>Programming with POSIX Threads</i>. Addison-Wesley.",
    "Chapman, B., Jost, G., &amp; van der Pas, R. (2008). <i>Using OpenMP: Portable Shared Memory Parallel Programming</i>. MIT Press.",
    "Gonzalez, R. C., &amp; Woods, R. E. (2018). <i>Digital Image Processing</i> (4th ed.). Pearson.",
    "Hennessy, J. L., &amp; Patterson, D. A. (2019). <i>Computer Architecture: A Quantitative Approach</i> (6th ed.). Morgan Kaufmann.",
    "Karp, A. H., &amp; Flatt, H. P. (1990). Measuring parallel processor performance. <i>Communications of the ACM</i>, 33(5), 539-543.",
    "OpenMP Architecture Review Board. (2021). <i>OpenMP Application Programming Interface, Version 5.2</i>. https://www.openmp.org",
    "Poskanzer, J. <i>PGM Format Specification</i>. Netpbm. https://netpbm.sourceforge.net/doc/pgm.html",
    "Sobel, I., &amp; Feldman, G. (1968). A 3x3 isotropic gradient operator for image processing. Presentasi pada Stanford Artificial Intelligence Project (SAIL).",
]
for i, r in enumerate(refs, 1):
    S.append(Paragraph(f"[{i}] {r}", ParagraphStyle("ref", parent=body, leftIndent=18, firstLineIndent=-18, alignment=0, spaceAfter=3)))

doc.build(S)
from pypdf import PdfReader
n = len(PdfReader(args.out).pages)
print(f"Laporan: {args.out} ({n} halaman){'  PERINGATAN: > 15 halaman!' if n > 15 else ''}")
