"""Colour vector of the downtown skyline, traced from the reference photo: the buildings are cut out of the sky with a
flood fill from the top edge, then quantised into a few flat colours (k-means in Lab) and each colour traced into
crisp paths, the way the bridges are flat fills. viewBox 600x230, ground at 230. Also writes the data-sky profile
and the night windows. Output: skyline.html (the markup) and skyline.css (the per-colour fills for day and night)."""
import cv2, numpy as np, random
random.seed(11)
SRC='/root/.claude/uploads/9f38b2cf-1489-5540-bb84-653f7bd5277e/2bf84454-image.png'
OUT='/tmp/claude-0/-home-claude/9f38b2cf-1489-5540-bb84-653f7bd5277e/scratchpad'
K=9                                   # flat colours
img=cv2.imread(SRC); H,W=img.shape[:2]
b,g,r=cv2.split(img); blue=b.astype(int)-r.astype(int)
rows=np.where((blue>40).mean(axis=1)>.85)[0]; rows=rows[rows>H*.5]; WL=int(rows.min())
# sky = everything the flood fill reaches from the top edge through the smooth gradient
bl=cv2.GaussianBlur(img,(5,5),0); m=np.zeros((H+2,W+2),np.uint8)
for x in range(0,W,20):
    if m[1,x+1]==0: cv2.floodFill(bl.copy(),m,(x,0),(255,255,255),(7,7,7),(7,7,7),cv2.FLOODFILL_MASK_ONLY|8)
sky=m[1:-1,1:-1]>0
build=(~sky).astype(np.uint8); build[WL:,:]=0
build=cv2.morphologyEx(build,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
col_top=np.full(W,WL)
for x in range(W):
    ys=np.where(build[:,x]>0)[0]
    if len(ys): col_top[x]=ys.min()
ct=col_top.copy()
for x in range(1,W-1):
    if col_top[x]<col_top[x-1]-25 and col_top[x]<col_top[x+1]-25: ct[x]=min(col_top[x-1],col_top[x+1])
col_top=ct; TOP=int(col_top.min())
S=600/W; VH=(WL-TOP)*S; Y0=230-VH
def vx(x): return x*S
def vy(y): return Y0+(y-TOP)*S
def fmt(v): s=f'{v:.1f}'; return s[:-2] if s.endswith('.0') else s
sil=np.zeros((H,W),np.uint8)
for x in range(W): sil[col_top[x]:WL,x]=1
# quantise the building pixels into K flat colours
lab=cv2.cvtColor(cv2.GaussianBlur(img,(3,3),0),cv2.COLOR_BGR2LAB)
pix=lab[sil==1].reshape(-1,3).astype(np.float32)
crit=(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,30,.5)
_,labels,centers=cv2.kmeans(pix,K,None,crit,4,cv2.KMEANS_PP_CENTERS)
lab_img=np.full((H,W),-1,np.int32); lab_img[sil==1]=labels.ravel()
# majority filter to merge speckle into flat regions
lab_u8=(lab_img+1).astype(np.uint8)
lab_u8=cv2.medianBlur(lab_u8,5); lab_img=lab_u8.astype(int)-1; lab_img[sil==0]=-1
# order colours darkest first so lighter shapes paint on top, and convert centres to hex
cent_bgr=cv2.cvtColor(centers.reshape(1,-1,3).astype(np.uint8),cv2.COLOR_LAB2BGR)[0]
order=np.argsort(centers[:,0])
def hexc(bgr): return '#%02x%02x%02x'%(bgr[2],bgr[1],bgr[0])
def trace(mask,eps,minarea):
    cs,_=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE); d=[]
    for c in cs:
        if cv2.contourArea(c)<minarea: continue
        a=cv2.approxPolyDP(c,eps,True)
        if len(a)<3: continue
        d.append('M'+' '.join(f'{fmt(vx(p[0][0]))} {fmt(vy(p[0][1]))}' for p in a)+'Z')
    return ' '.join(d)
# base silhouette in the darkest-but-one colour, then each colour's regions
cnt=np.array([[[x*1.0,col_top[x]*1.0]] for x in range(W)],np.float32); ap=cv2.approxPolyDP(cnt,1.0,False)
silpath='M0 230 L'+' '.join(f'{fmt(vx(p[0][0]))} {fmt(vy(p[0][1]))}' for p in ap)+' L600 230Z'
layers=[]; css_day=[]; css_night=[]
for i,ci in enumerate(order):
    mask=(lab_img==ci).astype(np.uint8)
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
    d=trace(mask,1.6,35)
    if not d: continue
    col=cent_bgr[ci].astype(int)
    layers.append(f'<path class="c{i}" d="{d}"/>')
    # day: the photo colour, pulled a little toward the haze so it sits behind the fog; night: the same hue, deep and desaturated
    hz=np.array([214,196,178])  # haze (BGR)
    day=(col*.78+hz*.22).astype(int)
    night=(col*.22+np.array([52,38,24])*.78).astype(int)
    css_day.append(f'.skyline .c{i}{{fill:{hexc(day)}}}')
    css_night.append(f'.skyline .c{i}{{fill:{hexc(night)}}}')
# windows (night): grid inside the silhouette, skipping the first rows under each roof
wins=[]
for x in range(3,597,4):
    px=min(W-1,int(x/S)); top=vy(col_top[px])
    for y in range(int(top)+4,229,5):
        py=int(TOP+(y-Y0)/S)
        if py>=WL or sil[py,px]==0: continue
        if random.random()<.3: wins.append(f'M{x} {y}h1.6v2.4h-1.6z')
dsky=[]
for k2 in range(61):
    c=k2*10; xs=range(max(0,int((c-5)/S)),min(W,int((c+5)/S)+1))
    dsky.append(str(int(min(vy(col_top[x]) for x in xs))))
bx=int(np.argmin(col_top)); beacon=(vx(bx),vy(col_top[bx])-2)
base_col=hexc((cent_bgr[order[1]]*.78+np.array([214,196,178])*.22).astype(int))
base_night=hexc((cent_bgr[order[1]]*.22+np.array([52,38,24])*.78).astype(int))
svg=(f'<div class="skyline" aria-hidden="true"><svg viewBox="0 0 600 230" preserveAspectRatio="xMidYMax meet" data-sky="{",".join(dsky)}" aria-hidden="true">'
     f'<path class="base" d="{silpath}"/>'+''.join(layers)+
     f'<path class="win" d="{" ".join(wins)}"/>'
     f'<circle class="beacon" cx="{beacon[0]:.1f}" cy="{beacon[1]:.1f}" r="1.6"/>'
     '</svg></div>')
open(OUT+'/skyline.html','w').write(svg)
open(OUT+'/skyline_day.css','w').write(f'.skyline .base{{fill:{base_col}}}'+''.join(css_day))
open(OUT+'/skyline_night.css','w').write(f'.skyline .base{{fill:{base_night}}}'+''.join(css_night))
print('bytes',len(svg),'layers',len(layers),'windows',len(wins),'viewBox h',round(VH,1))
print(open(OUT+'/skyline_day.css').read()); print(open(OUT+'/skyline_night.css').read())
