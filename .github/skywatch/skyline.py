"""Generates the downtown skyline SVG (viewBox 600x230, ground at y=230) and its data-sky
(top edge every 10 viewBox units, 61 values, 230 = nothing there), from one list of buildings."""
import random
random.seed(7)
G=230
# (x0, x1, top, kind) left to right as seen from the bay: Rincon/Embarcadero, 181 Fremont, Salesforce, Millennium,
# the Financial District boxes, Transamerica, Jackson Square, then Telegraph Hill with Coit Tower
B=[
 (14,44,152,'box'),(48,68,136,'box'),(72,102,118,'round'),(106,126,160,'box'),(130,156,126,'box'),
 (160,184,90,'spire'),(190,238,36,'crown'),(244,266,94,'box'),(270,296,112,'box'),(300,328,88,'box'),
 (332,356,120,'box'),(360,382,104,'box'),(386,406,142,'box'),(412,452,70,'pyramid'),(458,480,150,'box'),
 (484,504,164,'box'),(508,526,176,'box'),
]
HILL=[(520,205),(545,196),(570,190),(600,188)]   # Telegraph Hill, rising to the right edge
COIT=(556,566,134)                                # Coit Tower on the hill
paths=[]; wins=[]
def box(x0,x1,t): return f"M{x0} {G}V{t}H{x1}V{G}Z"
for x0,x1,t,k in B:
    w=x1-x0
    if k=='box': paths.append(box(x0,x1,t))
    elif k=='round': paths.append(f"M{x0} {G}V{t+6}Q{x0} {t} {x0+6} {t}H{x1-6}Q{x1} {t} {x1} {t+6}V{G}Z")
    elif k=='spire': m=(x0+x1)/2; paths.append(f"M{x0} {G}V{t+40}L{x0+3} {t+8}L{m-2} {t}L{m} {t-14}L{m+2} {t}L{x1-3} {t+8}L{x1} {t+40}V{G}Z")
    elif k=='crown': m=(x0+x1)/2; paths.append(f"M{x0} {G}V{t+60}C{x0} {t+20} {x0+8} {t+4} {m} {t}C{x1-8} {t+4} {x1} {t+20} {x1} {t+60}V{G}Z")
    elif k=='pyramid': m=(x0+x1)/2; paths.append(f"M{x0} {G}V{t+120}L{m-3} {t+4}L{m-1} {t-10}L{m+1} {t-10}L{m+3} {t+4}L{x1} {t+120}V{G}Z")
    # night windows: a sparse grid inside the wall, none on the tapering top
    if k in('box','round','spire','crown'):
        top=t+(60 if k=='crown' else 42 if k=='spire' else 10)
        for y in range(top, G-8, 7):
            for x in range(x0+3, x1-3, 5):
                if random.random()<.38: wins.append(f"M{x} {y}h2v3h-2z")
    elif k=='pyramid':
        for y in range(t+30, G-8, 7):
            half=(y-t)/120*(w/2)-3
            for x in range(int((x0+x1)/2-half), int((x0+x1)/2+half)-2, 5):
                if random.random()<.35: wins.append(f"M{x} {y}h2v3h-2z")
hill="M520 230V205"+"".join(f"L{x} {y}" for x,y in HILL[1:])+"V230Z"
cx0,cx1,ct=COIT; coit=f"M{cx0} 230V{ct+3}Q{cx0} {ct} {cx0+2} {ct}H{cx1-2}Q{cx1} {ct} {cx1} {ct+3}V230Z"
low="M0 230V210H14V230Z M44 230V214H48V230Z M68 230V212H72V230Z M126 230V200H130V230Z M156 230V204H160V230Z M184 230V206H190V230Z M238 230V198H244V230Z M266 230V204H270V230Z M296 230V208H300V230Z M328 230V202H332V230Z M356 230V210H360V230Z M382 230V206H386V230Z M406 230V196H412V230Z M452 230V204H458V230Z M480 230V206H484V230Z M504 230V208H508V230Z"
# data-sky: lowest y (highest top) in each 10-unit column, including spires and the hill
def topAt(x):
    t=G
    for x0,x1,tt,k in B:
        if x0<=x<=x1:
            if k=='spire' and abs(x-(x0+x1)/2)<=2: t=min(t,tt-14)
            elif k=='pyramid':
                m=(x0+x1)/2; d=abs(x-m); half=(x1-x0)/2
                t=min(t, tt-10 if d<=1 else tt+4+ (d-3)/(half-3)*120 if d>3 else tt+4)
            else: t=min(t,tt)
    if cx0<=x<=cx1: t=min(t,ct)
    for (xa,ya),(xb,yb) in zip(HILL,HILL[1:]):
        if xa<=x<=xb: t=min(t, ya+(yb-ya)*(x-xa)/(xb-xa))
    return t
sky=[]
for k in range(61):
    c=k*10; t=min(topAt(x) for x in range(max(0,c-5),min(600,c+5)+1))
    sky.append(str(int(t)))
svg=('<div class="skyline" aria-hidden="true"><svg viewBox="0 0 600 230" preserveAspectRatio="xMidYMax meet" data-sky="'+",".join(sky)+'" aria-hidden="true">'
     '<path class="city" d="'+" ".join(paths)+" "+hill+" "+coit+" "+low+'"/>'
     '<path class="win" d="'+" ".join(wins)+'"/>'
     '<circle class="beacon" cx="214" cy="33" r="1.6"/>'
     '</svg></div>')
open('/tmp/claude-0/-home-claude/9f38b2cf-1489-5540-bb84-653f7bd5277e/scratchpad/skyline.html','w').write(svg)
print(len(svg),'bytes;',len(wins),'windows; sky:',",".join(sky))
