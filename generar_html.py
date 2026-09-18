#!/usr/bin/env python3
"""
Generador HTML de Presupuestos por Proveedor
Escanea PROVEEDORES/ y genera proveedores.html.
Uso: python generar_html.py
"""
import sys, io, re, zlib, base64
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
            archivos = sorted([f.name for f in carpeta.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONES])
            if archivos:
                proveedores[carpeta.name] = archivos
    return proveedores


def extraer_logo_pdf(proveedor, base_dir):
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
                    w, h = int(obj.get("/Width", 0)), int(obj.get("/Height", 0))
                    if w < 50 or h < 50 or w > 2000 or h > 2000:
                        continue
                    data = obj.get_data()
                    filt = obj.get("/Filter", "")
                    if isinstance(filt, list):
                        filt = filt[0] if filt else ""
                    if filt == "/DCTDecode":
                        img = Image.open(BytesIO.BytesIO(data)).convert("RGBA")
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
                    w, h = int(obj.get("/Width", 0)), int(obj.get("/Height", 0))
                    if w < 50 or h < 50 or w > 2000 or h > 2000:
                        continue
                    filt_raw = obj.get("/Filter")
                    filt = str(filt_raw[0] if isinstance(filt_raw, pikepdf.Array) else filt_raw)
                    raw = bytes(obj.read_raw_bytes())
                    if "Flate" in filt:
                        data = zlib.decompress(raw)
                    elif "DCT" in filt:
                        img = Image.open(BytesIO.BytesIO(raw)).convert("RGBA")
                        img.thumbnail((200, 200), Image.LANCZOS)
                        img.save(str(icon_path), "PNG")
                        print(f"  Logo extraido: {proveedor} ({img.size[0]}x{img.size[1]})")
                        pdf_obj.close()
                        return True
                    else:
                        continue
                    cs = obj.get("/ColorSpace")
                    if isinstance(cs, pikepdf.Array) and "Indexed" in str(cs[0]):
                        pal_data = bytes(cs[3].get_object().read_raw_bytes())
                        img = Image.frombytes("P", (w, h), data)
                        lut = []
                        for j in range(0, min(len(pal_data), 768), 3):
                            lut.extend([pal_data[j], pal_data[j+1], pal_data[j+2]])
                        while len(lut) < 768:
                            lut.extend([0, 0, 0])
                        img.putpalette(lut)
                        img = img.convert("RGBA")
                    elif "RGB" in str(cs):
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
        if not (icons_dir / f"{proveedor}.png").exists():
            print(f"  Buscando logo para {proveedor}...")
            if extraer_logo_pdf(proveedor, base_dir):
                nuevos += 1
            else:
                print(f"  No se encontro logo para {proveedor}")
    return nuevos


def icono_html(proveedor):
    icon_path = SCRIPT_DIR / "icons" / f"{proveedor}.png"
    if icon_path.exists():
        b64 = base64.b64encode(icon_path.read_bytes()).decode()
        return '<img src="data:image/png;base64,' + b64 + '" style="width:40px;height:40px;object-fit:contain;border-radius:6px;">'
    return "&#128295;"


def get_file_icon(filename):
    ext = Path(filename).suffix.lower()
    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return '&#128247;'
    return '&#128196;'


def extraer_obra(nombre):
    match = re.search(r'\(([^)]+)\)', nombre)
    return match.group(1).strip() if match else "General"


def build_js():
    js = []
    js.append("var allPDFs=[],currentIndex=-1,isLocal=(location.protocol==='file:');")
    js.append("document.querySelectorAll('.pdf-item').forEach(function(el){allPDFs.push({url:el.getAttribute('data-pdf'),name:el.querySelector('.pdf-name').textContent,provider:el.closest('.proveedor-card').querySelector('.proveedor-name').textContent,element:el})});")
    # abrirPDF - detect file:// and open in new tab if local
    js.append("""function abrirPDF(url,name,provider){document.querySelectorAll('.pdf-item').forEach(function(e){e.classList.remove('active')});var item=document.querySelector('.pdf-item[data-pdf="'+url+'"]');if(item)item.classList.add('active');currentIndex=allPDFs.findIndex(function(p){return p.url===url});if(isLocal){window.open(url,'_blank');return}document.getElementById('viewer-overlay').classList.add('visible');document.body.style.overflow='hidden';document.getElementById('viewer-name').textContent=name;document.getElementById('viewer-provider').textContent=provider;var ext=url.split('.').pop().toLowerCase();var isImage=(ext==='jpg'||ext==='jpeg'||ext==='png'||ext==='gif'||ext==='webp');var frame=document.getElementById('viewer-frame');if(isImage){frame.style.background='white';frame.srcdoc='<html><body style="margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#f0f0f0"><img src="'+url+'" style="max-width:100%;max-height:100vh;object-fit:contain"></body></html>'}else{frame.style.background='#525659';frame.srcdoc='';frame.src=url}document.getElementById('btn-external').href=url;updateNav()}""")
    js.append("function cerrarPDF(){document.getElementById('viewer-overlay').classList.remove('visible');document.body.style.overflow='';var f=document.getElementById('viewer-frame');f.src='';f.srcdoc='';f.style.background='#525659';document.querySelectorAll('.pdf-item').forEach(function(e){e.classList.remove('active')});currentIndex=-1}")
    js.append("function navPDF(dir){if(currentIndex<0)return;var n=currentIndex+dir;if(n<0||n>=allPDFs.length)return;var p=allPDFs[n];abrirPDF(p.url,p.name,p.provider);var c=p.element.closest('.proveedor-card');c.querySelector('.proveedor-body').classList.add('open');c.querySelector('.proveedor-toggle').classList.add('open')}")
    js.append("function updateNav(){document.getElementById('btn-prev').disabled=currentIndex<=0;document.getElementById('btn-next').disabled=currentIndex>=allPDFs.length-1;document.getElementById('viewer-counter').textContent=(currentIndex+1)+'/'+allPDFs.length}")
    js.append("document.addEventListener('keydown',function(e){if(e.key==='Escape')cerrarPDF();if(e.key==='ArrowLeft')navPDF(-1);if(e.key==='ArrowRight')navPDF(1);if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();document.getElementById('searchInput').focus()}});")
    js.append("document.getElementById('viewer-overlay').addEventListener('click',function(e){if(e.target===this)cerrarPDF()});")
    js.append("function toggleProveedor(i){document.getElementById('body-'+i).classList.toggle('open');document.getElementById('toggle-'+i).classList.toggle('open')}")
    js.append("function expandirTodo(){document.querySelectorAll('.proveedor-body').forEach(function(e){e.classList.add('open')});document.querySelectorAll('.proveedor-toggle').forEach(function(e){e.classList.add('open')})}")
    js.append("function colapsarTodo(){document.querySelectorAll('.proveedor-body').forEach(function(e){e.classList.remove('open')});document.querySelectorAll('.proveedor-toggle').forEach(function(e){e.classList.remove('open')})}")
    js.append("var obraActual='todas';")
    js.append("function filtrarObra(obra,btn){obraActual=obra;document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active')});btn.classList.add('active');filtrar()}")
    js.append("""function filtrar(){var q=document.getElementById('searchInput').value.toLowerCase().trim();document.getElementById('clearBtn').classList.toggle('visible',q.length>0);var v=0;document.querySelectorAll('.pdf-item').forEach(function(item){var name=item.querySelector('.pdf-name').textContent.toLowerCase();var prov=item.closest('.proveedor-card').querySelector('.proveedor-name').textContent.toLowerCase();var obra=item.getAttribute('data-obra')||'';var matchSearch=q===''||name.includes(q)||prov.includes(q);var matchObra=obraActual==='todas'||obra===obraActual;if(matchSearch&&matchObra){item.style.display='flex';item.classList.remove('obra-hidden')}else{item.style.display='none';item.classList.add('obra-hidden')}});document.querySelectorAll('.proveedor-card').forEach(function(card){var pdfItems=card.querySelectorAll('.pdf-item');var visibles=0;pdfItems.forEach(function(item){if(!item.classList.contains('obra-hidden'))visibles++});var total=pdfItems.length;var countEl=card.querySelector('.proveedor-count');if(visibles===total){countEl.textContent=total+' presupuesto'+(total!==1?'s':'')}else{countEl.textContent=visibles+'/'+total+' presupuestos'}if(visibles>0||(q===''&&obraActual==='todas')){card.classList.remove('hidden','obra-hidden');v++;if(q.length>0||obraActual!=='todas'){card.querySelector('.proveedor-body').classList.add('open');card.querySelector('.proveedor-toggle').classList.add('open')}}else{card.classList.add('hidden')}});document.getElementById('emptyState').style.display=v===0?'block':'none'}""")
    js.append("function limpiarBusqueda(){document.getElementById('searchInput').value='';obraActual='todas';document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active')});document.querySelector('.filter-pill').classList.add('active');filtrar()}")
    return "\n".join(js)


def generar(proveedores):
    total_p = len(proveedores)
    total_pdfs = sum(len(p) for p in proveedores.values())

    todas_las_obras = set()
    for pdfs in proveedores.values():
        for pdf in pdfs:
            todas_las_obras.add(extraer_obra(Path(pdf).stem.strip()))
    obras_ordenadas = sorted(todas_las_obras)

    cards = []
    for i, (proveedor, pdfs) in enumerate(proveedores.items()):
        items = []
        for pdf in pdfs:
            url = ("PROVEEDORES/" + proveedor + "/" + pdf).replace("\\", "/")
            name = Path(pdf).stem.strip()
            obra = extraer_obra(name)
            url_enc = "/".join(quote(p, safe="") for p in url.split("/"))
            items.append(
                '<div class="pdf-item" onclick="abrirPDF(\'' + url_enc + '\',\'' + name.replace("'", "\\'") + '\',\'' + proveedor.replace("'", "\\'") + '\')" data-pdf="' + url_enc + '" data-obra="' + obra + '">'
                '<div class="pdf-icon">' + get_file_icon(pdf) + '</div>'
                '<div class="pdf-info"><div class="pdf-name">' + name + '</div><div class="pdf-size">' + obra + '</div></div>'
                '<div class="pdf-arrow">&#128196; Abrir</div></div>'
            )
        ct = str(len(pdfs)) + " presupuesto" + ("s" if len(pdfs) != 1 else "")
        cards.append(
            '<div class="proveedor-card" data-index="' + str(i) + '">'
            '<div class="proveedor-header" onclick="toggleProveedor(' + str(i) + ')">'
            '<div class="proveedor-left"><span class="proveedor-icon">' + icono_html(proveedor) + '</span>'
            '<div class="proveedor-info"><h3 class="proveedor-name">' + proveedor + '</h3>'
            '<span class="proveedor-count">' + ct + '</span></div></div>'
            '<div class="proveedor-toggle" id="toggle-' + str(i) + '">&#9660;</div></div>'
            '<div class="proveedor-body" id="body-' + str(i) + '"><div class="pdf-list">'
            + "\n".join(items)
            + '</div></div></div>'
        )

    obra_btns = ['<button class="filter-pill active" onclick="filtrarObra(\'todas\', this)">Todas</button>']
    for o in obras_ordenadas:
        obra_btns.append('<button class="filter-pill" onclick="filtrarObra(\'' + o.replace("'", "\\'") + '\', this)">' + o + '</button>')

    js = build_js()
    h = []
    h.append('<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    h.append('<title>Presupuestos - Proveedores | ECO STRUCT</title>\n<style>')
    h.append('* { margin:0; padding:0; box-sizing:border-box; }')
    h.append("body{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background:#f0f2f5;min-height:100vh;color:#333}")
    h.append('.header{background:linear-gradient(135deg,#2B3A4E 0%,#1a2533 100%);color:white;padding:30px 40px;box-shadow:0 4px 20px rgba(0,0,0,.15)}')
    h.append('.header-content{max-width:1100px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px}')
    h.append('.header h1{font-size:1.8rem;font-weight:700;display:flex;align-items:center;gap:12px}')
    h.append('.header-stats{display:flex;gap:24px}.stat{text-align:center}')
    h.append('.stat-value{font-size:1.6rem;font-weight:700;color:#4ecdc4}')
    h.append('.stat-label{font-size:.75rem;color:#8899aa;text-transform:uppercase;letter-spacing:.5px}')
    h.append('.search-bar{max-width:1100px;margin:24px auto 0;padding:0 40px}')
    h.append('.search-wrapper{position:relative}')
    h.append('.search-wrapper input{width:100%;padding:14px 20px 14px 48px;border:2px solid #e0e0e0;border-radius:12px;font-size:1rem;background:white;transition:border-color .3s,box-shadow .3s;outline:none}')
    h.append('.search-wrapper input:focus{border-color:#D4742C;box-shadow:0 0 0 3px rgba(212,116,44,.15)}')
    h.append('.search-icon{position:absolute;left:16px;top:50%;transform:translateY(-50%);font-size:1.2rem;color:#999}')
    h.append('.clear-btn{position:absolute;right:16px;top:50%;transform:translateY(-50%);background:none;border:none;font-size:1.2rem;color:#999;cursor:pointer;display:none}')
    h.append('.clear-btn.visible{display:block}')
    h.append('.container{max-width:1100px;margin:24px auto;padding:0 40px 40px}')
    h.append('.proveedor-card{background:white;border-radius:14px;margin-bottom:16px;box-shadow:0 2px 12px rgba(0,0,0,.06);overflow:hidden;transition:box-shadow .3s}')
    h.append('.proveedor-card:hover{box-shadow:0 4px 20px rgba(0,0,0,.1)}')
    h.append('.proveedor-card.hidden{display:none}')
    h.append('.proveedor-header{display:flex;justify-content:space-between;align-items:center;padding:20px 24px;cursor:pointer;user-select:none;transition:background .2s}')
    h.append('.proveedor-header:hover{background:#f8f9fa}')
    h.append('.proveedor-left{display:flex;align-items:center;gap:16px}')
    h.append('.proveedor-icon{font-size:2rem;width:50px;height:50px;display:flex;align-items:center;justify-content:center;background:#f0f4f8;border-radius:12px;overflow:hidden}')
    h.append('.proveedor-name{font-size:1.1rem;font-weight:600;color:#2B3A4E;margin:0}')
    h.append('.proveedor-count{font-size:.8rem;color:#888}')
    h.append('.proveedor-toggle{font-size:.9rem;color:#999;transition:transform .3s}')
    h.append('.proveedor-toggle.open{transform:rotate(180deg)}')
    h.append('.proveedor-body{max-height:0;overflow:hidden;transition:max-height .4s ease,padding .3s ease;padding:0 24px}')
    h.append('.proveedor-body.open{max-height:2000px;padding:0 24px 20px}')
    h.append('.pdf-list{border-top:1px solid #eee;padding-top:12px}')
    h.append('.pdf-item{display:flex;align-items:center;gap:14px;padding:14px 16px;border-radius:10px;text-decoration:none;color:inherit;transition:background .2s,transform .15s;margin-bottom:4px;cursor:pointer}')
    h.append('.pdf-item:hover{background:#fff8f0;transform:translateX(4px)}')
    h.append('.pdf-item.active{background:#fff3e8;border:2px solid #D4742C;transform:translateX(6px)}')
    h.append('.pdf-icon{font-size:1.6rem;width:40px;height:40px;display:flex;align-items:center;justify-content:center;background:#fee2e2;border-radius:10px;flex-shrink:0}')
    h.append('.pdf-item.active .pdf-icon{background:#D4742C}')
    h.append('.pdf-info{flex:1;min-width:0}')
    h.append('.pdf-name{font-weight:600;font-size:.92rem;color:#2B3A4E;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}')
    h.append('.pdf-size{font-size:.75rem;color:#999;margin-top:2px}')
    h.append('.pdf-arrow{font-size:1.2rem;color:#D4742C;opacity:0;transition:opacity .2s;flex-shrink:0}')
    h.append('.pdf-item:hover .pdf-arrow,.pdf-item.active .pdf-arrow{opacity:1}')
    h.append('.toolbar{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}')
    h.append('.toolbar-btn{padding:10px 20px;border:2px solid #e0e0e0;border-radius:10px;background:white;font-size:.85rem;font-weight:600;color:#555;cursor:pointer;transition:all .2s}')
    h.append('.toolbar-btn:hover{border-color:#D4742C;color:#D4742C}')
    h.append('.filter-bar{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;align-items:center}')
    h.append('.filter-label{font-size:.85rem;font-weight:600;color:#888;margin-right:4px}')
    h.append('.filter-pill{padding:8px 18px;border:2px solid #e0e0e0;border-radius:20px;background:white;font-size:.82rem;font-weight:600;color:#555;cursor:pointer;transition:all .2s}')
    h.append('.filter-pill:hover{border-color:#D4742C;color:#D4742C}')
    h.append('.filter-pill.active{background:#D4742C;border-color:#D4742C;color:white}')
    h.append('.pdf-item.obra-hidden{display:none !important}')
    h.append('.empty-state{text-align:center;padding:60px 20px;color:#999}')
    h.append('.empty-state .emoji{font-size:3rem;margin-bottom:12px}')
    h.append('.footer{text-align:center;padding:20px;color:#aaa;font-size:.75rem}')
    h.append('#viewer-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:1000;animation:fadeIn .3s ease}')
    h.append('#viewer-overlay.visible{display:flex;flex-direction:column}')
    h.append('@keyframes fadeIn{from{opacity:0}to{opacity:1}}')
    h.append('.viewer-bar{background:#2B3A4E;color:white;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}')
    h.append('.viewer-title{font-size:.95rem;font-weight:600;display:flex;align-items:center;gap:10px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}')
    h.append('.viewer-actions{display:flex;gap:10px;flex-shrink:0}')
    h.append('.viewer-btn{padding:8px 16px;border-radius:8px;border:none;font-size:.85rem;font-weight:600;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:6px}')
    h.append('.viewer-btn-close{background:#e74c3c;color:white}.viewer-btn-close:hover{background:#c0392b}')
    h.append('.viewer-btn-external{background:#4ecdc4;color:#1a2533;text-decoration:none}.viewer-btn-external:hover{background:#45b7af}')
    h.append('.viewer-btn-nav{background:rgba(255,255,255,.15);color:white}.viewer-btn-nav:hover{background:rgba(255,255,255,.25)}')
    h.append('.viewer-btn-nav:disabled{opacity:.3;cursor:default}')
    h.append('.viewer-frame{flex:1;border:none;background:#525659}')
    h.append('@media(max-width:600px){.header{padding:20px}.header h1{font-size:1.3rem}.container,.search-bar{padding:0 16px}.viewer-bar{padding:10px 16px}.viewer-btn{padding:6px 10px;font-size:.8rem}}')
    h.append('.local-hint{text-align:center;background:#fff3e8;color:#D4742C;padding:12px 20px;border-radius:10px;margin-bottom:20px;font-size:.85rem;font-weight:600;display:none}')
    h.append('</style>\n</head>\n<body>')
    h.append('<div class="header"><div class="header-content"><h1>&#128203; Presupuestos por Proveedor</h1><div class="header-stats">')
    h.append('<div class="stat"><div class="stat-value">' + str(total_p) + '</div><div class="stat-label">Proveedores</div></div>')
    h.append('<div class="stat"><div class="stat-value">' + str(total_pdfs) + '</div><div class="stat-label">Presupuestos</div></div>')
    h.append('</div></div></div>')
    h.append('<div class="search-bar"><div class="search-wrapper">')
    h.append('<span class="search-icon">&#128269;</span>')
    h.append('<input type="text" id="searchInput" placeholder="Buscar proveedor o presupuesto..." oninput="filtrar()">')
    h.append('<button class="clear-btn" id="clearBtn" onclick="limpiarBusqueda()">&#10005;</button>')
    h.append('</div></div>')
    h.append('<div class="container">')
    # Hint for local users
    h.append('<div class="local-hint" id="localHint">&#9888; Estas en modo local. Los PDFs se abren en una pestana nueva. Para verlos integrados, ejecuta ver.bat</div>')
    h.append('<div class="toolbar">')
    h.append('<button class="toolbar-btn" onclick="expandirTodo()">&#128194; Expandir todo</button>')
    h.append('<button class="toolbar-btn" onclick="colapsarTodo()">&#128193; Colapsar todo</button>')
    h.append('</div><div class="filter-bar"><span class="filter-label">Obra:</span>')
    h.append("\n".join(obra_btns))
    h.append('</div><div id="proveedoresList">')
    h.append("\n".join(cards))
    h.append('</div><div class="empty-state" id="emptyState" style="display:none"><div class="emoji">&#128269;</div><p>No se encontraron resultados</p></div></div>')
    h.append('<div class="footer">Presupuestos Proveedores &middot; ECO STRUCT &middot; Generado automaticamente</div>')
    h.append('<div id="viewer-overlay"><div class="viewer-bar"><div class="viewer-title">')
    h.append('<span>&#128196;</span><span id="viewer-name">...</span>')
    h.append('<span style="color:#8899aa;font-weight:400;font-size:.85rem">|</span>')
    h.append('<span id="viewer-provider" style="color:#4ecdc4;font-weight:400;font-size:.85rem"></span></div>')
    h.append('<div class="viewer-actions">')
    h.append('<button class="viewer-btn viewer-btn-nav" id="btn-prev" onclick="navPDF(-1)" title="Anterior">&#9664; Ant</button>')
    h.append('<span id="viewer-counter" style="color:#8899aa;font-size:.85rem;display:flex;align-items:center;min-width:40px;justify-content:center"></span>')
    h.append('<button class="viewer-btn viewer-btn-nav" id="btn-next" onclick="navPDF(1)" title="Siguiente">Sig &#9654;</button>')
    h.append('<a id="btn-external" href="#" target="_blank" class="viewer-btn viewer-btn-external" title="Abrir en pestana">&#128269; Pestana</a>')
    h.append('<button class="viewer-btn viewer-btn-close" onclick="cerrarPDF()" title="Cerrar">&times; Cerrar</button>')
    h.append('</div></div><iframe id="viewer-frame" class="viewer-frame"></iframe></div>')
    # Add JS to show local hint
    extra_js = '\nif(isLocal)document.getElementById("localHint").style.display="block";'
    h.append('<script>\n' + js + extra_js + '\n</script>\n</body>\n</html>')
    return "\n".join(h)


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
