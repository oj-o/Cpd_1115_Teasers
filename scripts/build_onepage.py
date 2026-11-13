"""index.html(예고편)에 film.html(흑백 애니메이션) 재생기를 그대로 합쳐 한 페이지로 만든다.
film.html을 고친 뒤 `python scripts/build_onepage.py`를 다시 실행하면 index.html의 흑백 구역이 갱신된다.
- film.html의 클래스/ID에 f- 접두사를 붙이고, CSS는 #f-app 안으로 가두고, 스크립트는 즉시실행함수로 감싼다.
"""
import re,pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent
idx=(ROOT/'index.html').read_text()
film=(ROOT/'film.html').read_text()
START,END='<!-- FILM:START -->','<!-- FILM:END -->'

# ---------- film CSS → #f-app 범위 ----------
css=film[film.index('<style>')+7:film.index('</style>')]
css=re.sub(r'/\*.*?\*/','',css,flags=re.S)
def cls(sel):return re.sub(r'\.([A-Za-z][\w-]*)',lambda m:'.f-'+m.group(1),sel)
out=[]
for block in css.split('}'):
    if '{' not in block:continue
    sel,body=block.split('{',1);sel=sel.strip()
    if not sel:continue
    parts=[]
    for one in sel.split(','):
        one=one.strip()
        if one in(':root',):parts.append('#f-app');continue
        if one in('html','body','html,body','[hidden]') or one.startswith('.embed') or one.startswith('.sitenav') or one=='body.embed':continue
        parts.append('#f-app '+cls(one))
    if parts:out.append(','.join(parts)+'{'+body.strip()+'}')
fcss='\n'.join(out)+'\n#f-app{background:var(--ink);color:var(--paper);font-family:var(--ui);padding:22px max(16px,env(safe-area-inset-left,0px)) 28px;margin:30px calc(-1*max(16px,env(safe-area-inset-left,0px))) 0;border-top:1px solid #2b2b2b}'

# ---------- film 마크업 ----------
body=film[film.index('<div class="wrap">'):film.index('\n<script>')]
body=body[:body.rindex('</div>')]                       # wrap 닫기 전까지
body=re.sub(r'\s*<section class="dl".*?</section>','',body,flags=re.S)   # 다운로드는 페이지 맨 아래 통합 구역 사용
body=re.sub(r'class="([^"]+)"',lambda m:'class="'+' '.join('f-'+c for c in m.group(1).split())+'"',body)
body=re.sub(r'id="([^"]+)"',lambda m:'id="f-'+m.group(1)+'"',body)
body=body.replace('<div class="f-wrap">','<div class="f-wrap" id="f-app-inner">',1)
markup=f'<section id="f-app" aria-label="흑백 애니메이션">\n<span id="film" style="position:relative;top:-12px"></span>\n{body}</div>\n</section>'

# ---------- film 스크립트 ----------
js=film[film.index('<script>')+8:film.rindex('</script>')]
js=js.replace("$=id=>document.getElementById(id)","$=id=>document.getElementById('f-'+id)")
js=js.replace("document.getElementById('cv')","document.getElementById('f-cv')")
for a,b in [("'.tabs button'","'#f-app .f-tabs button'"),("'.mode button'","'#f-app .f-mode button'"),("'.syn article'","'#f-app .f-syn article'"),
            ("'details.chars'","'#f-app details.f-chars'"),("classList.toggle('on',a.id==='syn-'+k)","classList.toggle('f-on',a.id==='f-syn-'+k)")]:
    assert a in js,a;js=js.replace(a,b)
js=js.replace("document.addEventListener('keydown',e=>{if(e.target.matches('input,button'))return;","document.addEventListener('keydown',e=>{if(e.target.matches('input,button'))return;if(window.__active!=='film')return;",1)
js=js.replace("function play(){","function play(){window.__pauseTeaser&&window.__pauseTeaser();",1)
js=js.replace("function pause(){","window.__pauseFilm=()=>{if(st.playing)pause()};function pause(){",1)
js=js.replace("try{localStorage.setItem('jeoseung-film',k);localStorage.setItem('jeoseung-mode',st.mode)}catch(e){}","try{localStorage.setItem('jeoseung-film',k);localStorage.setItem('jeoseung-mode',st.mode)}catch(e){}",1)
script='<script>\n(()=>{\n'+js+'\n})();\n</script>'

block=f'{START}\n<style>\n{fcss}\n</style>\n{markup}\n{script}\n{END}'
if START in idx:
    idx=idx[:idx.index(START)]+block+idx[idx.index(END)+len(END):]
else:
    k=idx.index('<section class="alldl"');idx=idx[:k]+block+'\n\n'+idx[k:]
(ROOT/'index.html').write_text(idx)
print('built',len(idx))
