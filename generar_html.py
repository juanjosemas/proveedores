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

EXTENSIONES = ('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp')


def escanear(base_dir):
    proveedores = {}
    base = Path(base_dir)
    if not base.exists():
        print(f"No se encuentra: {base_dir}")
        sys.exit(1)
    for carpeta in sorted(base.iterdir()):
        if carpeta.is_dir() and not carpeta.name.startswith('.'):
            pdfs = sorted([f.name for f in carpeta.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONES])
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

    if icon_path.exists():
        return True

    prov_dir = base_dir / proveedor
    pdfs = sorted(prov_dir.glob("*.pdf"))
    if not pdfs:
        return False

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
    icon_path = SCRIPT_DIR / "icons" / f"{proveedor}.png"
    if icon_path.exists():
        with open(icon_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return '<img src="data:image/png;base64,' + b64 + '" style="width:40px;height:40px;object-fit:contain;border-radius:6px;">'
    u = proveedor.upper()
    if "ELECTRIC" in u or "FERRIS" in u: return "&#9889;"
    if "CLIMA" in u or "GOCLIMA" in u: return "&#10052;"
    if "ACAV" in u: return "&#128682;"
    return "&#128295;"


def get_file_icon(filename):
    ext = Path(filename).suffix.lower()
    if ext == '.pdf':
        return '&#128196;'
    elif ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return '&#128247;'
    return '&#128196;'


def extraer_obra(nombre_pdf):
    match = re.search(r'\(([^)]+)\)', nombre_pdf)
    return match.group(1).strip() if match else "General"


def js_string():
    """Build the JavaScript block cleanly, avoiding Python string escaping issues."""
    lines = []
    lines.append("var allPDFs=[],currentIndex=-1;")
    lines.append("document.querySelectorAll('.pdf-item').forEach(function(el){allPDFs.push({url:el.getAttribute('data-pdf'),name:el.querySelector('.pdf-name').textContent,provider:el.closest('.proveedor-card').querySelector('.proveedor-name').textContent,element:el})});")
    # abrirPDF - use string check instead of regex for image detection
    lines.append("""function abrirPDF(url,name,provider){document.querySelectorAll('.pdf-item').forEach(function(e){e.classList.remove('active')});var item=document.querySelector('.pdf-item[data-pdf="'+url+'"]');if(item)item.classList.add('active');currentIndex=allPDFs.findIndex(function(p){return p.url===url});document.getElementById('viewer-overlay').classList.add('visible');document.body.style.overflow='hidden';document.getElementById('viewer-name').textContent=name;document.getElementById('viewer-provider').textContent=provider;var ext=url.split('.').pop().toLowerCase();var isImage=(ext==='jpg'||ext==='jpeg'||ext==='png'||ext==='gif'||ext==='webp');var frame=document.getElementById('viewer-frame');if(isImage){frame.style.background='white';frame.srcdoc='<html><body style="margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#f0f0f0"><img src="'+url+'" style="max-width:100%;max-height:100vh;object-fit:contain"></body></html>'}else{frame.style.background='#525659';frame.srcdoc='';frame.src=url}document.getElementById('btn-external').href=url;updateNav()}""")
    lines.append("function cerrarPDF(){document.getElementById('viewer-overlay').classList.remove('visible');document.body.style.overflow='';var frame=document.getElementById('viewer-frame');frame.src='';frame.srcdoc='';frame.style.background='#525659';document.querySelectorAll('.pdf-item').forEach(function(e){e.classList.remove('active')});currentIndex=-1}")
    lines.append("function navPDF(dir){if(currentIndex<0)return;var next=currentIndex+dir;if(next<0||next>=allPDFs.length)return;var p=allPDFs[next];abrirPDF(p.url,p.name,p.provider);var card=p.element.closest('.proveedor-card');card.querySelector('.proveedor-body').classList.add('open');card.querySelector('.proveedor-toggle').classList.add('open')}")
    lines.append("function updateNav(){document.getElementById('btn-prev').disabled=currentIndex<=0;document.getElementById('btn-next').disabled=currentIndex>=allPDFs.length-1;document.getElementById('viewer-counter').textContent=(currentIndex+1)+'/'+allPDFs.length}")
    lines.append("document.addEventListener('keydown',function(e){if(e.key==='Escape')cerrarPDF();if(e.key==='ArrowLeft')navPDF(-1);if(e.key==='ArrowRight')navPDF(1);if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();document.getElementById('searchInput').focus()}});")
    lines.append("document.getElementById('viewer-overlay').addEventListener('click',function(e){if(e.target===this)cerrarPDF()});")
    lines.append("function toggleProveedor(i){document.getElementById('body-'+i).classList.toggle('open');document.getElementById('toggle-'+i).classList.toggle('open')}")
    lines.append("function expandirTodo(){document.querySelectorAll('.proveedor-body').forEach(function(e){e.classList.add('open')});document.querySelectorAll('.proveedor-toggle').forEach(function(e){e.classList.add('open')})}")
    lines.append("function colapsarTodo(){document.querySelectorAll('.proveedor-body').forEach(function(e){e.classList.remove('open')});document.querySelectorAll('.proveedor-toggle').forEach(function(e){e.classList.remove('open')})}")
    # filtrar
    lines.append("var obraActual='todas';")
    lines.append("function filtrarObra(obra,btn){obraActual=obra;document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active')});btn.classList.add('active');filtrar()}")
    lines.append("""function filtrar(){var q=document.getElementById('searchInput').value.toLowerCase().trim();document.getElementById('clearBtn').classList.toggle('visible',q.length>0);var v=0;document.querySelectorAll('.pdf-item').forEach(function(item){var name=item.querySelector('.pdf-name').textContent.toLowerCase();var obra=item.getAttribute('data-obra')||'';var matchSearch=q===''||name.includes(q);var matchObra=obraActual==='todas'||obra===obraActual;if(matchSearch&&matchObra){item.style.display='flex';item.classList.remove('obra-hidden')}else{item.style.display='none';item.classList.add('obra-hidden')}});document.querySelectorAll('.proveedor-card').forEach(function(card){var pdfItems=card.querySelectorAll('.pdf-item');var visibles=0;pdfItems.forEach(function(item){if(!item.classList.contains('obra-hidden'))visibles++});var total=pdfItems.length;var countEl=card.querySelector('.proveedor-count');if(visibles===total){countEl.textContent=total+' presupuesto'+(total!==1?'s':'')}else{countEl.textContent=visibles+'/'+total+' presupuestos'}if(visibles>0||(q===''&&obraActual==='todas')){card.classList.remove('hidden','obra-hidden');v++;if(q.length>0||obraActual!=='todas'){card.querySelector('.proveedor-body').classList.add('open');card.querySelector('.proveedor-toggle').classList.add('open')}}else{card.classList.add('hidden')}});document.getElementById('emptyState').style.display=v===0?'block':'none'}""")
    # limpiarBusqueda
    lines.append("function limpiarBusqueda(){document.getElementById('searchInput').value='';obraActual='todas';document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active')});document.querySelector('.filter-pill').classList.add('active');filtrar();ocultarDropdown()}")
    # Dropdown autocomplete
    lines.append("var provedoresNombres=[];document.querySelectorAll('.proveedor-card').forEach(function(c){provedoresNombres.push(c.querySelector('.proveedor-name').textContent)});")
    lines.append("function mostrarDropdown(){var q=document.getElementById('searchInput').value.trim();if(q.length>0)actualizarDropdown(q);else ocultarDropdown()}")
    lines.append("function ocultarDropdown(){setTimeout(function(){document.getElementById('searchDropdown').classList.remove('visible')},200)}")
    # actualizarDropdown - use data-idx attributes instead of escaping quotes in onclick
    lines.append("""function actualizarDropdown(q){var dd=document.getElementById('searchDropdown');var ql=q.toLowerCase();var provs=[];var docs=[];provedoresNombres.forEach(function(name,i){if(name.toLowerCase().indexOf(ql)!==-1)provs.push({name:name,idx:i})});document.querySelectorAll('.pdf-item').forEach(function(el){var name=el.querySelector('.pdf-name').textContent;if(name.toLowerCase().indexOf(ql)!==-1){var prov=el.closest('.proveedor-card').querySelector('.proveedor-name').textContent;var obra=el.getAttribute('data-obra')||'';var url=el.getAttribute('data-pdf');docs.push({name:name,prov:prov,obra:obra,url:url})}});if(provs.length===0&&docs.length===0){dd.classList.remove('visible');return}var html='';if(provs.length>0){html+='<div class="dropdown-section">Proveedores</div>';provs.slice(0,5).forEach(function(p){var h=p.name.replace(new RegExp('('+q.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')+')','gi'),'<mark>$1</mark>');html+='<div class="dropdown-item" data-prov-idx="'+p.idx+'"><div class="dropdown-item-icon prov">&#128188;</div><div class="dropdown-item-text"><div class="dropdown-item-name">'+h+'</div></div></div>'})}if(docs.length>0){html+='<div class="dropdown-section">Presupuestos</div>';docs.slice(0,8).forEach(function(d){var h=d.name.replace(new RegExp('('+q.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')+')','gi'),'<mark>$1</mark>');html+='<div class="dropdown-item" data-doc-url="'+d.url+'"><div class="dropdown-item-icon doc">&#128196;</div><div class="dropdown-item-text"><div class="dropdown-item-name">'+h+'</div><div class="dropdown-item-sub">'+d.prov+(d.obra!=='General'?' | '+d.obra:'')+'</div></div></div>'})}if(provs.length>5||docs.length>8){html+='<div class="dropdown-section" style="color:#D4742C;">...y mas resultados. Escribe mas para filtrar</div>'}dd.innerHTML=html;dd.classList.add('visible')}""")
    # Event delegation for dropdown clicks
    lines.append("""document.getElementById('searchDropdown').addEventListener('click',function(e){var item=e.target.closest('.dropdown-item');if(!item)return;var provIdx=item.getAttribute('data-prov-idx');var docUrl=item.getAttribute('data-doc-url');if(provIdx!==null){seleccionarProveedor(provedoresNombres[parseInt(provIdx)])}else if(docUrl!==null){seleccionarDocumento(docUrl)}});""")
    lines.append("function seleccionarProveedor(name){document.getElementById('searchInput').value='';document.getElementById('searchDropdown').classList.remove('visible');document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active')});document.querySelector('.filter-pill').classList.add('active');obraActual='todas';document.querySelectorAll('.pdf-item').forEach(function(item){item.style.display='flex';item.classList.remove('obra-hidden')});document.querySelectorAll('.proveedor-card').forEach(function(card){card.classList.remove('hidden','obra-hidden')});var showed=false;document.querySelectorAll('.proveedor-card').forEach(function(card){if(card.querySelector('.proveedor-name').textContent===name){card.classList.add('open');card.querySelector('.proveedor-body').classList.add('open');card.querySelector('.proveedor-toggle').classList.add('open');var total=card.querySelectorAll('.pdf-item').length;card.querySelector('.proveedor-count').textContent=total+' presupuesto'+(total!==1?'s':'');showed=true}else{card.classList.add('hidden')}});document.getElementById('emptyState').style.display=showed?'none':'block';document.getElementById('clearBtn').classList.remove('visible')}")
    lines.append("""function seleccionarDocumento(url){document.getElementById('searchDropdown').classList.remove('visible');var item=document.querySelector('.pdf-item[data-pdf="'+url+'"]');if(item){var card=item.closest('.proveedor-card');card.querySelector('.proveedor-body').classList.add('open');card.querySelector('.proveedor-toggle').classList.add('open');var name=item.querySelector('.pdf-name').textContent;var prov=card.querySelector('.proveedor-name').textContent;abrirPDF(url,name,prov)}}""")
    lines.append("document.getElementById('searchInput').addEventListener('blur',ocultarDropdown);")
    lines.append("document.getElementById('searchInput').addEventListener('focus',function(){var q=this.value.trim();if(q.length>0)mostrarDropdown()})")
    return "\n".join(lines)


def generar(proveedores):
    total_p = len(proveedores)
    total_pdfs = sum(len(p) for p in proveedores.values())

    todas_las_obras = set()
    for pdfs in proveedores.values():
        for pdf in pdfs:
            name_no_ext = Path(pdf).stem.strip()
            todas_las_obras.add(extraer_obra(name_no_ext))
    obras_ordenadas = sorted(todas_las_obras)

    cards = ""
    for i, (proveedor, pdfs) in enumerate(proveedores.items()):
        items = ""
        for pdf in pdfs:
            url = f"PROVEEDORES/{proveedor}/{pdf}".replace("\\", "/")
            name = Path(pdf).stem.strip()
            obra = extraer_obra(name)
            url_enc = "/".join(quote(p, safe="") for p in url.split("/"))
            safe_name = name.replace("'", "\\'")
            safe_prov = proveedor.replace("'", "\\'")
            safe_obra = obra.replace("'", "\\'")
            items += '\n          <div class="pdf-item" onclick="abrirPDF(\'' + url_enc + '\',\'' + safe_name + '\',\'' + safe_prov + '\')" data-pdf="' + url_enc + '" data-obra="' + safe_obra + '">\n            <div class="pdf-icon">' + get_file_icon(pdf) + '</div>\n            <div class="pdf-info">\n              <div class="pdf-name">' + name + '</div>\n              <div class="pdf-size">' + obra + '</div>\n            </div>\n            <div class="pdf-arrow">&#128196; Abrir</div>\n          </div>'

        count_text = str(len(pdfs)) + " presupuesto" + ("s" if len(pdfs) != 1 else "")
        cards += '\n    <div class="proveedor-card" data-index="' + str(i) + '">\n'
        cards += '      <div class="proveedor-header" onclick="toggleProveedor(' + str(i) + ')">\n'
        cards += '        <div class="proveedor-left">\n'
        cards += '          <span class="proveedor-icon">' + icono_html(proveedor) + '</span>\n'
        cards += '          <div class="proveedor-info">\n'
        cards += '            <h3 class="proveedor-name">' + proveedor + '</h3>\n'
        cards += '            <span class="proveedor-count">' + count_text + '</span>\n'
        cards += '          </div>\n'
        cards += '        </div>\n'
        cards += '        <div class="proveedor-toggle" id="toggle-' + str(i) + '">&#9660;</div>\n'
        cards += '      </div>\n'
        cards += '      <div class="proveedor-body" id="body-' + str(i) + '">\n'
        cards += '        <div class="pdf-list">' + items + '\n        </div>\n'
        cards += '      </div>\n'
        cards += '    </div>'

    # Build obra filter buttons
    obra_buttons = '\n    <button class="filter-pill active" onclick="filtrarObra(\'todas\', this)">Todas</button>'
    for o in obras_ordenadas:
        safe_o = o.replace("'", "\\'")
        obra_buttons += "\n    " + '<button class="filter-pill" onclick="filtrarObra(\'' + safe_o + '\', this)">' + o + '</button>'

    # Build the full HTML using string concatenation (not f-strings with JS)
    js = js_string()

    html = '<!DOCTYPE html>\n<html lang="es">\n<head>\n'
    html += '<meta charset="UTF-8">\n'
    html += '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    html += '<title>Presupuestos - Proveedores | ECO STRUCT</title>\n'
    html += '<style>\n'
    html += '  * { margin: 0; padding: 0; box-sizing: border-box; }\n'
    html += "  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; min-height: 100vh; color: #333; }\n"
    html += "  .header { background: linear-gradient(135deg, #2B3A4E 0%, #1a2533 100%); color: white; padding: 30px 40px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); }\n"
    html += "  .header-content { max-width: 1100px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }\n"
    html += "  .header h1 { font-size: 1.8rem; font-weight: 700; display: flex; align-items: center; gap: 12px; }\n"
    html += "  .header-stats { display: flex; gap: 24px; }\n"
    html += "  .stat { text-align: center; }\n"
    html += "  .stat-value { font-size: 1.6rem; font-weight: 700; color: #4ecdc4; }\n"
    html += "  .stat-label { font-size: 0.75rem; color: #8899aa; text-transform: uppercase; letter-spacing: 0.5px; }\n"
    html += "  .search-bar { max-width: 1100px; margin: 24px auto 0; padding: 0 40px; }\n"
    html += "  .search-wrapper { position: relative; }\n"
    html += "  .search-wrapper input { width: 100%; padding: 14px 20px 14px 48px; border: 2px solid #e0e0e0; border-radius: 12px; font-size: 1rem; background: white; transition: border-color 0.3s, box-shadow 0.3s; outline: none; }\n"
    html += "  .search-wrapper input:focus { border-color: #D4742C; box-shadow: 0 0 0 3px rgba(212,116,44,0.15); }\n"
    html += "  .search-icon { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.2rem; color: #999; }\n"
    html += "  .clear-btn { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); background: none; border: none; font-size: 1.2rem; color: #999; cursor: pointer; display: none; }\n"
    html += "  .clear-btn.visible { display: block; }\n"
    html += "  .search-dropdown { position: absolute; top: 100%; left: 0; right: 0; background: white; border: 2px solid #e0e0e0; border-top: none; border-radius: 0 0 12px 12px; max-height: 320px; overflow-y: auto; z-index: 100; display: none; box-shadow: 0 8px 24px rgba(0,0,0,0.12); }\n"
    html += "  .search-dropdown.visible { display: block; }\n"
    html += "  .dropdown-section { padding: 8px 16px 4px; font-size: 0.72rem; font-weight: 700; color: #999; text-transform: uppercase; letter-spacing: 0.5px; }\n"
    html += "  .dropdown-item { display: flex; align-items: center; gap: 12px; padding: 10px 16px; cursor: pointer; transition: background 0.15s; }\n"
    html += "  .dropdown-item:hover { background: #fff8f0; }\n"
    html += "  .dropdown-item-icon { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 8px; flex-shrink: 0; font-size: 1.1rem; }\n"
    html += "  .dropdown-item-icon.prov { background: #e8f4fd; }\n"
    html += "  .dropdown-item-icon.doc { background: #fee2e2; }\n"
    html += "  .dropdown-item-text { flex: 1; min-width: 0; }\n"
    html += "  .dropdown-item-name { font-weight: 600; font-size: 0.88rem; color: #2B3A4E; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n"
    html += "  .dropdown-item-sub { font-size: 0.75rem; color: #999; }\n"
    html += "  .dropdown-item-name mark { background: #fff3e8; color: #D4742C; border-radius: 2px; padding: 0 1px; }\n"
    html += "  .container { max-width: 1100px; margin: 24px auto; padding: 0 40px 40px; }\n"
    html += "  .proveedor-card { background: white; border-radius: 14px; margin-bottom: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); overflow: hidden; transition: box-shadow 0.3s; }\n"
    html += "  .proveedor-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.1); }\n"
    html += "  .proveedor-card.hidden { display: none; }\n"
    html += "  .proveedor-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; cursor: pointer; user-select: none; transition: background 0.2s; }\n"
    html += "  .proveedor-header:hover { background: #f8f9fa; }\n"
    html += "  .proveedor-left { display: flex; align-items: center; gap: 16px; }\n"
    html += "  .proveedor-icon { font-size: 2rem; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; background: #f0f4f8; border-radius: 12px; overflow: hidden; }\n"
    html += "  .proveedor-name { font-size: 1.1rem; font-weight: 600; color: #2B3A4E; margin: 0; }\n"
    html += "  .proveedor-count { font-size: 0.8rem; color: #888; }\n"
    html += "  .proveedor-toggle { font-size: 0.9rem; color: #999; transition: transform 0.3s; }\n"
    html += "  .proveedor-toggle.open { transform: rotate(180deg); }\n"
    html += "  .proveedor-body { max-height: 0; overflow: hidden; transition: max-height 0.4s ease, padding 0.3s ease; padding: 0 24px; }\n"
    html += "  .proveedor-body.open { max-height: 2000px; padding: 0 24px 20px; }\n"
    html += "  .pdf-list { border-top: 1px solid #eee; padding-top: 12px; }\n"
    html += "  .pdf-item { display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-radius: 10px; text-decoration: none; color: inherit; transition: background 0.2s, transform 0.15s; margin-bottom: 4px; cursor: pointer; }\n"
    html += "  .pdf-item:hover { background: #fff8f0; transform: translateX(4px); }\n"
    html += "  .pdf-item.active { background: #fff3e8; border: 2px solid #D4742C; transform: translateX(6px); }\n"
    html += "  .pdf-icon { font-size: 1.6rem; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; background: #fee2e2; border-radius: 10px; flex-shrink: 0; }\n"
    html += "  .pdf-item.active .pdf-icon { background: #D4742C; }\n"
    html += "  .pdf-info { flex: 1; min-width: 0; }\n"
    html += "  .pdf-name { font-weight: 600; font-size: 0.92rem; color: #2B3A4E; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n"
    html += "  .pdf-size { font-size: 0.75rem; color: #999; margin-top: 2px; }\n"
    html += "  .pdf-arrow { font-size: 1.2rem; color: #D4742C; opacity: 0; transition: opacity 0.2s; flex-shrink: 0; }\n"
    html += "  .pdf-item:hover .pdf-arrow, .pdf-item.active .pdf-arrow { opacity: 1; }\n"
    html += "  .toolbar { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }\n"
    html += "  .toolbar-btn { padding: 10px 20px; border: 2px solid #e0e0e0; border-radius: 10px; background: white; font-size: 0.85rem; font-weight: 600; color: #555; cursor: pointer; transition: all 0.2s; }\n"
    html += "  .toolbar-btn:hover { border-color: #D4742C; color: #D4742C; }\n"
    html += "  .filter-bar { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }\n"
    html += "  .filter-label { font-size: 0.85rem; font-weight: 600; color: #888; margin-right: 4px; }\n"
    html += "  .filter-pill { padding: 8px 18px; border: 2px solid #e0e0e0; border-radius: 20px; background: white; font-size: 0.82rem; font-weight: 600; color: #555; cursor: pointer; transition: all 0.2s; }\n"
    html += "  .filter-pill:hover { border-color: #D4742C; color: #D4742C; }\n"
    html += "  .filter-pill.active { background: #D4742C; border-color: #D4742C; color: white; }\n"
    html += "  .pdf-item.obra-hidden { display: none !important; }\n"
    html += "  .proveedor-card.obra-hidden { display: none; }\n"
    html += "  .empty-state { text-align: center; padding: 60px 20px; color: #999; }\n"
    html += "  .empty-state .emoji { font-size: 3rem; margin-bottom: 12px; }\n"
    html += "  .footer { text-align: center; padding: 20px; color: #aaa; font-size: 0.75rem; }\n"
    html += "  #viewer-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 1000; animation: fadeIn 0.3s ease; }\n"
    html += "  #viewer-overlay.visible { display: flex; flex-direction: column; }\n"
    html += "  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }\n"
    html += "  .viewer-bar { background: #2B3A4E; color: white; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }\n"
    html += "  .viewer-title { font-size: 0.95rem; font-weight: 600; display: flex; align-items: center; gap: 10px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }\n"
    html += "  .viewer-actions { display: flex; gap: 10px; flex-shrink: 0; }\n"
    html += "  .viewer-btn { padding: 8px 16px; border-radius: 8px; border: none; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }\n"
    html += "  .viewer-btn-close { background: #e74c3c; color: white; }\n"
    html += "  .viewer-btn-close:hover { background: #c0392b; }\n"
    html += "  .viewer-btn-external { background: #4ecdc4; color: #1a2533; text-decoration: none; }\n"
    html += "  .viewer-btn-external:hover { background: #45b7af; }\n"
    html += "  .viewer-btn-nav { background: rgba(255,255,255,0.15); color: white; }\n"
    html += "  .viewer-btn-nav:hover { background: rgba(255,255,255,0.25); }\n"
    html += "  .viewer-btn-nav:disabled { opacity: 0.3; cursor: default; }\n"
    html += "  .viewer-frame { flex: 1; border: none; background: #525659; }\n"
    html += "  @media (max-width: 600px) { .header { padding: 20px; } .header h1 { font-size: 1.3rem; } .container, .search-bar { padding: 0 16px; } .viewer-bar { padding: 10px 16px; } .viewer-btn { padding: 6px 10px; font-size: 0.8rem; } }\n"
    html += '</style>\n</head>\n<body>\n\n'

    html += '<div class="header">\n  <div class="header-content">\n'
    html += '    <h1>&#128203; Presupuestos por Proveedor</h1>\n'
    html += '    <div class="header-stats">\n'
    html += '      <div class="stat"><div class="stat-value">' + str(total_p) + '</div><div class="stat-label">Proveedores</div></div>\n'
    html += '      <div class="stat"><div class="stat-value">' + str(total_pdfs) + '</div><div class="stat-label">Presupuestos</div></div>\n'
    html += '    </div>\n  </div>\n</div>\n\n'

    html += '<div class="search-bar">\n  <div class="search-wrapper">\n'
    html += '    <span class="search-icon">&#128269;</span>\n'
    html += '    <input type="text" id="searchInput" placeholder="Buscar proveedor o presupuesto..." oninput="filtrar();actualizarDropdown(this.value)" onfocus="mostrarDropdown()" autocomplete="off">\n'
    html += '    <button class="clear-btn" id="clearBtn" onclick="limpiarBusqueda()">&#10005;</button>\n'
    html += '    <div class="search-dropdown" id="searchDropdown"></div>\n'
    html += '  </div>\n</div>\n\n'

    html += '<div class="container">\n'
    html += '  <div class="toolbar">\n'
    html += '    <button class="toolbar-btn" onclick="expandirTodo()">&#128194; Expandir todo</button>\n'
    html += '    <button class="toolbar-btn" onclick="colapsarTodo()">&#128193; Colapsar todo</button>\n'
    html += '  </div>\n'
    html += '  <div class="filter-bar">\n'
    html += '    <span class="filter-label">Obra:</span>\n'
    html += obra_buttons + '\n'
    html += '  </div>\n'
    html += '  <div id="proveedoresList">' + cards + '\n  </div>\n'
    html += '  <div class="empty-state" id="emptyState" style="display:none">\n'
    html += '    <div class="emoji">&#128269;</div>\n'
    html += '    <p>No se encontraron resultados</p>\n'
    html += '  </div>\n</div>\n\n'

    html += '<div class="footer">Presupuestos Proveedores &middot; ECO STRUCT &middot; Generado automaticamente</div>\n\n'

    html += '<div id="viewer-overlay">\n'
    html += '  <div class="viewer-bar">\n'
    html += '    <div class="viewer-title">\n'
    html += '      <span>&#128196;</span>\n'
    html += '      <span id="viewer-name">...</span>\n'
    html += '      <span style="color:#8899aa;font-weight:400;font-size:0.85rem">|</span>\n'
    html += '      <span id="viewer-provider" style="color:#4ecdc4;font-weight:400;font-size:0.85rem"></span>\n'
    html += '    </div>\n'
    html += '    <div class="viewer-actions">\n'
    html += '      <button class="viewer-btn viewer-btn-nav" id="btn-prev" onclick="navPDF(-1)" title="Anterior">&#9664; Ant</button>\n'
    html += '      <span id="viewer-counter" style="color:#8899aa;font-size:0.85rem;display:flex;align-items:center;min-width:40px;justify-content:center"></span>\n'
    html += '      <button class="viewer-btn viewer-btn-nav" id="btn-next" onclick="navPDF(1)" title="Siguiente">Sig &#9654;</button>\n'
    html += '      <a id="btn-external" href="#" target="_blank" class="viewer-btn viewer-btn-external" title="Abrir en pestana">&#128269; Pestana</a>\n'
    html += '      <button class="viewer-btn viewer-btn-close" onclick="cerrarPDF()" title="Cerrar">&times; Cerrar</button>\n'
    html += '    </div>\n'
    html += '  </div>\n'
    html += '  <iframe id="viewer-frame" class="viewer-frame"></iframe>\n'
    html += '</div>\n\n'

    html += '<script>\n' + js + '\n</script>\n'
    html += '</body>\n</html>'

    return html


def main():
    print("Escaneando PROVEEDORES...")
    proveedores = escanear(PROVEEDORES_DIR)
    if not proveedores:
        print("No se encontraron proveedores con PDFs.")
        sys.exit(1)

    total = sum(len(p) for p in proveedores.values())
    print(f"  {len(proveedores)} proveedores, {total} presupuestos")

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
