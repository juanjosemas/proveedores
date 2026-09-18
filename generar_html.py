#!/usr/bin/env python3
"""
Generador HTML de Presupuestos por Proveedor
=============================================
Escanea PROVEEDORES/ y genera proveedores.html.
Sin servidor, sin abrir navegador.

Uso: python generar_html.py
"""

import sys
import io
import re
import zlib
import base64
from pathlib import Path
from urllib.parse import quote

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

SCRIPT_DIR = Path(__file__).resolve().parent
PROVEEDORES_DIR = SCRIPT_DIR / "PROVEEDORES"


def escanear(base_dir):
    proveedores = {}
    base = Path(base_dir)
    if not base.exists():
        print(f"No se encuentra: {base_dir}")
        sys.exit(1)
    for carpeta in sorted(base.iterdir()):
        if carpeta.is_dir() and not carpeta.name.startswith('.'):
            pdfs = sorted([f.name for f in carpeta.iterdir() if f.is_file() and f.suffix.lower() == '.pdf'])
            if pdfs:
                proveedores[carpeta.name] = pdfs
    return proveedores


def extraer_logo_pdf(proveedor, base_dir):
    """Extrae el logo del primer PDF de un proveedor y lo guarda en icons/"""
    from PIL import Image
    import io as BytesIO
    
    icons_dir = SCRIPT_DIR / "icons"
    icons_dir.mkdir(exist_ok=True)
    icon_path = icons_dir / f"{proveedor}.png"
    
    # Si ya existe el logo, no extraer de nuevo
    if icon_path.exists():
        return True
    
    prov_dir = base_dir / proveedor
    pdfs = sorted(prov_dir.glob("*.pdf"))
    if not pdfs:
        return False
    
    # Intentar con PyPDF2 primero (DCTDecode/JPEG)
    try:
        import PyPDF2
        for pdf in pdfs:
            try:
                reader = PyPDF2.PdfReader(str(pdf))
                page = reader.pages[0]
                res = page["/Resources"].get_object()
                if "/XObject" not in res:
                    continue
                xobjects = res["/XObject"].get_object()
                for obj_name in xobjects:
                    obj = xobjects[obj_name].get_object()
                    if obj["/Subtype"] != "/Image":
                        continue
                    w = int(obj.get("/Width", 0))
                    h = int(obj.get("/Height", 0))
                    if w < 50 or h < 50 or w > 2000 or h > 2000:
                        continue
                    data = obj.get_data()
                    filt = obj.get("/Filter", "")
                    if isinstance(filt, list):
                        filt = filt[0] if filt else ""
                    if filt == "/DCTDecode":
                        img = Image.open(BytesIO.BytesIO(data))
                        img = img.convert("RGBA")
                        img.thumbnail((200, 200), Image.LANCZOS)
                        img.save(str(icon_path), "PNG")
                        print(f"  Logo extraido: {proveedor} ({img.size[0]}x{img.size[1]})")
                        return True
            except Exception:
                continue
    except ImportError:
        pass
    
    # Intentar con pikepdf (RunLength, Flate, indexed)
    try:
        import pikepdf
        for pdf in pdfs:
            try:
                pdf_obj = pikepdf.open(str(pdf))
                page = pdf_obj.pages[0]
                res = page.get("/Resources")
                if res is None:
                    continue
                res = res.get_object()
                if "/XObject" not in res:
                    continue
                xobjects = res["/XObject"].get_object()
                for obj_name in xobjects:
                    obj = xobjects[obj_name].get_object()
                    if obj.get("/Subtype") != "/Image":
                        continue
                    w = int(obj.get("/Width", 0))
                    h = int(obj.get("/Height", 0))
                    if w < 50 or h < 50 or w > 2000 or h > 2000:
                        continue
                    
                    filt_raw = obj.get("/Filter")
                    if isinstance(filt_raw, pikepdf.Array):
                        filt = filt_raw[0]
                    else:
                        filt = filt_raw
                    filt = str(filt)
                    
                    raw = bytes(obj.read_raw_bytes())
                    
                    # Descomprimir
                    if "Flate" in filt:
                        data = zlib.decompress(raw)
                    elif "RunLength" in filt:
                        result = bytearray()
                        i = 0
                        while i < len(raw):
                            length = raw[i]; i += 1
                            if length == 128: break
                            if length < 128:
                                result.extend(raw[i:i+length+1]); i += length+1
                            else:
                                byte = raw[i]; i += 1
                                result.extend([byte]*(257-length))
                        data = bytes(result)
                    elif "DCT" in filt:
                        img = Image.open(BytesIO.BytesIO(raw))
                        img = img.convert("RGBA")
                        img.thumbnail((200, 200), Image.LANCZOS)
                        img.save(str(icon_path), "PNG")
                        print(f"  Logo extraido: {proveedor} ({img.size[0]}x{img.size[1]})")
                        pdf_obj.close()
                        return True
                    else:
                        continue
                    
                    # Indexed palette
                    cs = obj.get("/ColorSpace")
                    if isinstance(cs, pikepdf.Array) and "Indexed" in str(cs[0]):
                        pal_obj = cs[3]
                        pal_data = bytes(pal_obj.read_raw_bytes())
                        palette_img = Image.frombytes("P", (w, h), data)
                        lut = []
                        for j in range(0, min(len(pal_data), 768), 3):
                            lut.extend([pal_data[j], pal_data[j+1], pal_data[j+2]])
                        while len(lut) < 768: lut.extend([0,0,0])
                        palette_img.putpalette(lut)
                        img = palette_img.convert("RGBA")
                    elif "RGB" in str(cs):
                        img = Image.frombytes("RGB", (w, h), data).convert("RGBA")
                    elif "Gray" in str(cs):
                        img = Image.frombytes("L", (w, h), data).convert("RGBA")
                    else:
                        bands = len(data) // (w * h)
                        if bands == 3:
                            img = Image.frombytes("RGB", (w, h), data).convert("RGBA")
                        else:
                            img = Image.frombytes("L", (w, h), data).convert("RGBA")
                    
                    img.thumbnail((200, 200), Image.LANCZOS)
                    img.save(str(icon_path), "PNG")
                    print(f"  Logo extraido: {proveedor} ({img.size[0]}x{img.size[1]})")
                    pdf_obj.close()
                    return True
                pdf_obj.close()
            except Exception:
                continue
    except ImportError:
        pass
    
    return False


def extraer_logos_automatico(proveedores, base_dir):
    """Extrae logos para todos los proveedores que no tengan logo"""
    icons_dir = SCRIPT_DIR / "icons"
    icons_dir.mkdir(exist_ok=True)
    nuevos = 0
    for proveedor in proveedores:
        icon_path = icons_dir / f"{proveedor}.png"
        if not icon_path.exists():
            print(f"  Buscando logo para {proveedor}...")
            if extraer_logo_pdf(proveedor, base_dir):
                nuevos += 1
            else:
                print(f"  No se encontro logo para {proveedor}")
    return nuevos


def icono_html(proveedor):
    """Return base64 img tag if logo exists, else emoji fallback"""
    icon_path = SCRIPT_DIR / "icons" / f"{proveedor}.png"
    if icon_path.exists():
        with open(icon_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="width:40px;height:40px;object-fit:contain;border-radius:6px;">'
    u = proveedor.upper()
    if "ELECTRIC" in u or "FERRIS" in u: return "&#9889;"
    if "CLIMA" in u or "GOCLIMA" in u: return "&#10052;"
    if "ACAV" in u: return "&#128682;"
    return "&#128295;"


def extraer_obra(nombre_pdf):
    """Extrae la obra del nombre del PDF, e.g. 'MOSQUITERAS  (FORMENTERA 14)' -> 'FORMENTERA 14'"""
    match = re.search(r'\(([^)]+)\)', nombre_pdf)
    return match.group(1).strip() if match else "General"


def generar(proveedores):
    total_p = len(proveedores)
    total_pdfs = sum(len(p) for p in proveedores.values())

    # Collect all unique obras
    todas_las_obras = set()
    for pdfs in proveedores.values():
        for pdf in pdfs:
            todas_las_obras.add(extraer_obra(pdf.replace(".pdf", "").strip()))
    obras_ordenadas = sorted(todas_las_obras)

    cards = ""
    for i, (proveedor, pdfs) in enumerate(proveedores.items()):
        items = ""
        for pdf in pdfs:
            url = f"PROVEEDORES/{proveedor}/{pdf}".replace("\\", "/")
            name = pdf.replace(".pdf", "").strip()
            obra = extraer_obra(name)
            url_enc = "/".join(quote(p, safe="") for p in url.split("/"))
            safe_name = name.replace("'", "\\'")
            safe_prov = proveedor.replace("'", "\\'")
            safe_obra = obra.replace("'", "\\'")
            items += f'''
          <div class="pdf-item" onclick="abrirPDF('{url_enc}','{safe_name}','{safe_prov}')" data-pdf="{url_enc}" data-obra="{safe_obra}">
            <div class="pdf-icon">&#128196;</div>
            <div class="pdf-info">
              <div class="pdf-name">{name}</div>
              <div class="pdf-size">{obra}</div>
            </div>
            <div class="pdf-arrow">&#128196; Abrir</div>
          </div>'''
        
        # Count visible PDFs (will be updated by JS but set initial count)
        visible_count = len(pdfs)

        cards += f'''
    <div class="proveedor-card" data-index="{i}">
      <div class="proveedor-header" onclick="toggleProveedor({i})">
        <div class="proveedor-left">
          <span class="proveedor-icon">{icono_html(proveedor)}</span>
          <div class="proveedor-info">
            <h3 class="proveedor-name">{proveedor}</h3>
            <span class="proveedor-count">{len(pdfs)} presupuesto{"s" if len(pdfs) != 1 else ""}</span>
          </div>
        </div>
        <div class="proveedor-toggle" id="toggle-{i}">&#9660;</div>
      </div>
      <div class="proveedor-body" id="body-{i}">
        <div class="pdf-list">{items}
        </div>
      </div>
    </div>'''

    html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Presupuestos - Proveedores | ECO STRUCT</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; min-height: 100vh; color: #333; }
  .header { background: linear-gradient(135deg, #2B3A4E 0%, #1a2533 100%); color: white; padding: 30px 40px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); }
  .header-content { max-width: 1100px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }
  .header h1 { font-size: 1.8rem; font-weight: 700; display: flex; align-items: center; gap: 12px; }
  .header-stats { display: flex; gap: 24px; }
  .stat { text-align: center; }
  .stat-value { font-size: 1.6rem; font-weight: 700; color: #4ecdc4; }
  .stat-label { font-size: 0.75rem; color: #8899aa; text-transform: uppercase; letter-spacing: 0.5px; }
  .search-bar { max-width: 1100px; margin: 24px auto 0; padding: 0 40px; }
  .search-wrapper { position: relative; }
  .search-wrapper input { width: 100%; padding: 14px 20px 14px 48px; border: 2px solid #e0e0e0; border-radius: 12px; font-size: 1rem; background: white; transition: border-color 0.3s, box-shadow 0.3s; outline: none; }
  .search-wrapper input:focus { border-color: #D4742C; box-shadow: 0 0 0 3px rgba(212,116,44,0.15); }
  .search-icon { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.2rem; color: #999; }
  .clear-btn { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); background: none; border: none; font-size: 1.2rem; color: #999; cursor: pointer; display: none; }
  .clear-btn.visible { display: block; }
  .container { max-width: 1100px; margin: 24px auto; padding: 0 40px 40px; }
  .proveedor-card { background: white; border-radius: 14px; margin-bottom: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); overflow: hidden; transition: box-shadow 0.3s; }
  .proveedor-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
  .proveedor-card.hidden { display: none; }
  .proveedor-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; cursor: pointer; user-select: none; transition: background 0.2s; }
  .proveedor-header:hover { background: #f8f9fa; }
  .proveedor-left { display: flex; align-items: center; gap: 16px; }
  .proveedor-icon { font-size: 2rem; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; background: #f0f4f8; border-radius: 12px; overflow: hidden; }
  .proveedor-name { font-size: 1.1rem; font-weight: 600; color: #2B3A4E; margin: 0; }
  .proveedor-count { font-size: 0.8rem; color: #888; }
  .proveedor-toggle { font-size: 0.9rem; color: #999; transition: transform 0.3s; }
  .proveedor-toggle.open { transform: rotate(180deg); }
  .proveedor-body { max-height: 0; overflow: hidden; transition: max-height 0.4s ease, padding 0.3s ease; padding: 0 24px; }
  .proveedor-body.open { max-height: 2000px; padding: 0 24px 20px; }
  .pdf-list { border-top: 1px solid #eee; padding-top: 12px; }
  .pdf-item { display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-radius: 10px; text-decoration: none; color: inherit; transition: background 0.2s, transform 0.15s; margin-bottom: 4px; cursor: pointer; }
  .pdf-item:hover { background: #fff8f0; transform: translateX(4px); }
  .pdf-item.active { background: #fff3e8; border: 2px solid #D4742C; transform: translateX(6px); }
  .pdf-icon { font-size: 1.6rem; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; background: #fee2e2; border-radius: 10px; flex-shrink: 0; }
  .pdf-item.active .pdf-icon { background: #D4742C; }
  .pdf-info { flex: 1; min-width: 0; }
  .pdf-name { font-weight: 600; font-size: 0.92rem; color: #2B3A4E; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pdf-size { font-size: 0.75rem; color: #999; margin-top: 2px; }
  .pdf-arrow { font-size: 1.2rem; color: #D4742C; opacity: 0; transition: opacity 0.2s; flex-shrink: 0; }
  .pdf-item:hover .pdf-arrow, .pdf-item.active .pdf-arrow { opacity: 1; }
  .toolbar { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
  .toolbar-btn { padding: 10px 20px; border: 2px solid #e0e0e0; border-radius: 10px; background: white; font-size: 0.85rem; font-weight: 600; color: #555; cursor: pointer; transition: all 0.2s; }
  .toolbar-btn:hover { border-color: #D4742C; color: #D4742C; }
  .filter-bar { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
  .filter-label { font-size: 0.85rem; font-weight: 600; color: #888; margin-right: 4px; }
  .filter-pill { padding: 8px 18px; border: 2px solid #e0e0e0; border-radius: 20px; background: white; font-size: 0.82rem; font-weight: 600; color: #555; cursor: pointer; transition: all 0.2s; }
  .filter-pill:hover { border-color: #D4742C; color: #D4742C; }
  .filter-pill.active { background: #D4742C; border-color: #D4742C; color: white; }
  .pdf-item.obra-hidden { display: none !important; }
  .proveedor-card.obra-hidden { display: none; }
  .empty-state { text-align: center; padding: 60px 20px; color: #999; }
  .empty-state .emoji { font-size: 3rem; margin-bottom: 12px; }
  .footer { text-align: center; padding: 20px; color: #aaa; font-size: 0.75rem; }
  #viewer-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 1000; animation: fadeIn 0.3s ease; }
  #viewer-overlay.visible { display: flex; flex-direction: column; }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  .viewer-bar { background: #2B3A4E; color: white; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
  .viewer-title { font-size: 0.95rem; font-weight: 600; display: flex; align-items: center; gap: 10px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  .viewer-actions { display: flex; gap: 10px; flex-shrink: 0; }
  .viewer-btn { padding: 8px 16px; border-radius: 8px; border: none; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }
  .viewer-btn-close { background: #e74c3c; color: white; }
  .viewer-btn-close:hover { background: #c0392b; }
  .viewer-btn-external { background: #4ecdc4; color: #1a2533; text-decoration: none; }
  .viewer-btn-external:hover { background: #45b7af; }
  .viewer-btn-nav { background: rgba(255,255,255,0.15); color: white; }
  .viewer-btn-nav:hover { background: rgba(255,255,255,0.25); }
  .viewer-btn-nav:disabled { opacity: 0.3; cursor: default; }
  .viewer-frame { flex: 1; border: none; background: #525659; }
  @media (max-width: 600px) { .header { padding: 20px; } .header h1 { font-size: 1.3rem; } .container, .search-bar { padding: 0 16px; } .viewer-bar { padding: 10px 16px; } .viewer-btn { padding: 6px 10px; font-size: 0.8rem; } }
</style>
</head>
<body>

<div class="header">
  <div class="header-content">
    <h1>&#128203; Presupuestos por Proveedor</h1>
    <div class="header-stats">
      <div class="stat"><div class="stat-value">""" + str(total_p) + """</div><div class="stat-label">Proveedores</div></div>
      <div class="stat"><div class="stat-value">""" + str(total_pdfs) + """</div><div class="stat-label">Presupuestos</div></div>
    </div>
  </div>
</div>

<div class="search-bar">
  <div class="search-wrapper">
    <span class="search-icon">&#128269;</span>
    <input type="text" id="searchInput" placeholder="Buscar proveedor o presupuesto..." oninput="filtrar()">
    <button class="clear-btn" id="clearBtn" onclick="limpiarBusqueda()">&#10005;</button>
  </div>
</div>

<div class="container">
  <div class="toolbar">
    <button class="toolbar-btn" onclick="expandirTodo()">&#128194; Expandir todo</button>
    <button class="toolbar-btn" onclick="colapsarTodo()">&#128193; Colapsar todo</button>
  </div>
  <div class="filter-bar">
    <span class="filter-label">Obra:</span>
    <button class="filter-pill active" onclick="filtrarObra('todas', this)">Todas</button>""" + "\n".join(f'\n    <button class="filter-pill" onclick="filtrarObra(\'{o}\', this)">{o}</button>' for o in obras_ordenadas) + """
  </div>
  <div id="proveedoresList">""" + cards + """
  </div>
  <div class="empty-state" id="emptyState" style="display:none">
    <div class="emoji">&#128269;</div>
    <p>No se encontraron resultados</p>
  </div>
</div>

<div class="footer">Presupuestos Proveedores &middot; ECO STRUCT &middot; Generado automaticamente</div>

<div id="viewer-overlay">
  <div class="viewer-bar">
    <div class="viewer-title">
      <span>&#128196;</span>
      <span id="viewer-name">...</span>
      <span style="color:#8899aa;font-weight:400;font-size:0.85rem">|</span>
      <span id="viewer-provider" style="color:#4ecdc4;font-weight:400;font-size:0.85rem"></span>
    </div>
    <div class="viewer-actions">
      <button class="viewer-btn viewer-btn-nav" id="btn-prev" onclick="navPDF(-1)" title="Anterior">&#9664; Ant</button>
      <span id="viewer-counter" style="color:#8899aa;font-size:0.85rem;display:flex;align-items:center;min-width:40px;justify-content:center"></span>
      <button class="viewer-btn viewer-btn-nav" id="btn-next" onclick="navPDF(1)" title="Siguiente">Sig &#9654;</button>
      <a id="btn-external" href="#" target="_blank" class="viewer-btn viewer-btn-external" title="Abrir en pestana">&#128269; Pestana</a>
      <button class="viewer-btn viewer-btn-close" onclick="cerrarPDF()" title="Cerrar">&times; Cerrar</button>
    </div>
  </div>
  <iframe id="viewer-frame" class="viewer-frame"></iframe>
</div>

<script>
var allPDFs=[],currentIndex=-1;
document.querySelectorAll('.pdf-item').forEach(function(el){allPDFs.push({url:el.getAttribute('data-pdf'),name:el.querySelector('.pdf-name').textContent,provider:el.closest('.proveedor-card').querySelector('.proveedor-name').textContent,element:el})});
function abrirPDF(url,name,provider){document.querySelectorAll('.pdf-item').forEach(function(e){e.classList.remove('active')});var item=document.querySelector('.pdf-item[data-pdf="'+url+'"]');if(item)item.classList.add('active');currentIndex=allPDFs.findIndex(function(p){return p.url===url});document.getElementById('viewer-overlay').classList.add('visible');document.body.style.overflow='hidden';document.getElementById('viewer-name').textContent=name;document.getElementById('viewer-provider').textContent=provider;document.getElementById('viewer-frame').src=url;document.getElementById('btn-external').href=url;updateNav()}
function cerrarPDF(){document.getElementById('viewer-overlay').classList.remove('visible');document.body.style.overflow='';document.getElementById('viewer-frame').src='';document.querySelectorAll('.pdf-item').forEach(function(e){e.classList.remove('active')});currentIndex=-1}
function navPDF(dir){if(currentIndex<0)return;var next=currentIndex+dir;if(next<0||next>=allPDFs.length)return;var p=allPDFs[next];abrirPDF(p.url,p.name,p.provider);var card=p.element.closest('.proveedor-card');card.querySelector('.proveedor-body').classList.add('open');card.querySelector('.proveedor-toggle').classList.add('open')}
function updateNav(){document.getElementById('btn-prev').disabled=currentIndex<=0;document.getElementById('btn-next').disabled=currentIndex>=allPDFs.length-1;document.getElementById('viewer-counter').textContent=(currentIndex+1)+'/'+allPDFs.length}
document.addEventListener('keydown',function(e){if(e.key==='Escape')cerrarPDF();if(e.key==='ArrowLeft')navPDF(-1);if(e.key==='ArrowRight')navPDF(1);if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();document.getElementById('searchInput').focus()}});
document.getElementById('viewer-overlay').addEventListener('click',function(e){if(e.target===this)cerrarPDF()});
function toggleProveedor(i){document.getElementById('body-'+i).classList.toggle('open');document.getElementById('toggle-'+i).classList.toggle('open')}
function expandirTodo(){document.querySelectorAll('.proveedor-body').forEach(function(e){e.classList.add('open')});document.querySelectorAll('.proveedor-toggle').forEach(function(e){e.classList.add('open')})}
function colapsarTodo(){document.querySelectorAll('.proveedor-body').forEach(function(e){e.classList.remove('open')});document.querySelectorAll('.proveedor-toggle').forEach(function(e){e.classList.remove('open')})}
var obraActual='todas';
function filtrarObra(obra,btn){obraActual=obra;document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active')});btn.classList.add('active');filtrar()}
function filtrar(){var q=document.getElementById('searchInput').value.toLowerCase().trim();document.getElementById('clearBtn').classList.toggle('visible',q.length>0);var v=0;
document.querySelectorAll('.pdf-item').forEach(function(item){var name=item.querySelector('.pdf-name').textContent.toLowerCase();var obra=item.getAttribute('data-obra')||'';var matchSearch=q===''||name.includes(q);var matchObra=obraActual==='todas'||obra===obraActual;if(matchSearch&&matchObra){item.style.display='flex';item.classList.remove('obra-hidden')}else{item.style.display='none';item.classList.add('obra-hidden')}});
document.querySelectorAll('.proveedor-card').forEach(function(card){var nombre=card.querySelector('.proveedor-name').textContent.toLowerCase();var pdfItems=card.querySelectorAll('.pdf-item');var visibles=0;pdfItems.forEach(function(item){if(!item.classList.contains('obra-hidden'))visibles++});var total=pdfItems.length;var countEl=card.querySelector('.proveedor-count');if(visibles===total){countEl.textContent=total+' presupuesto'+(total!==1?'s':'')}else{countEl.textContent=visibles+'/'+total+' presupuestos'}if(visibles>0||(q===''&&obraActual==='todas')){card.classList.remove('hidden','obra-hidden');v++;if(q.length>0||obraActual!=='todas'){card.querySelector('.proveedor-body').classList.add('open');card.querySelector('.proveedor-toggle').classList.add('open')}}else{card.classList.add('hidden')}});
document.getElementById('emptyState').style.display=v===0?'block':'none'}
function limpiarBusqueda(){document.getElementById('searchInput').value='';obraActual='todas';document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active')});document.querySelector('.filter-pill').classList.add('active');filtrar()}
</script>
</body></html>"""
    return html


def main():
    print("Escaneando PROVEEDORES...")
    proveedores = escanear(PROVEEDORES_DIR)
    if not proveedores:
        print("No se encontraron proveedores con PDFs.")
        sys.exit(1)

    total = sum(len(p) for p in proveedores.values())
    print(f"  {len(proveedores)} proveedores, {total} presupuestos")

    # Extraer logos automaticamente para proveedores nuevos
    print("Extrayendo logos...")
    nuevos = extraer_logos_automatico(proveedores, PROVEEDORES_DIR)
    if nuevos > 0:
        print(f"  {nuevos} logo(s) nuevo(s) extraido(s)")
    else:
        print("  Todos los logos ya estaban extraidos")

    html = generar(proveedores)
    out = SCRIPT_DIR / "proveedores.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Creado: {out}")
    print("Listo! Abre proveedores.html en el navegador.")


if __name__ == "__main__":
    main()
