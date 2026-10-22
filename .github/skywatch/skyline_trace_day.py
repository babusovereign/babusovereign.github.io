"""Day skyline, detailed trace of the rendered reference (the other agent's own rendering, so no licence to carry).
The city is cut from the sky with a flood fill, sky-coloured rims along the roofline are dropped, the facades are
quantised into K flat colours with only light smoothing and traced at a fine tolerance, and an ink layer traced from
the building edges puts the window grids, setbacks and tower edges back. viewBox 600x230, ground at 230.
Writes skyline_day.html (markup with inline fills) and prints the size."""
import cv2, numpy as np
SRC='/root/.claude/uploads/9f38b2cf-1489-5540-bb84-653f7bd5277e/2bf84454-image.png'
OUT='/tmp/claude-0/-home-claude/9f38b2cf-1489-5540-bb84-653f7bd5277e/scratchpad'
K=14; EPS=1.1
img=cv2.imread(SRC); img=cv2.resize(img,(1300,int(img.shape[0]*1300/img.shape[1])),interpolation=cv2.INTER_AREA); H,W=img.shape[:2]
b,g,r=cv2.split(img); blue=b.astype(int)-r.astype(int)
rows=np.where((blue>40).mean(axis=1)>.85)[0]; rows=rows[rows>H*.5]; WL=int(rows.min())
V=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)[:,:,2]
bl=cv2.GaussianBlur(img,(5,5),0); m=np.zeros((H+2,W+2),np.uint8)
for x in range(0,W,20):
    if m[1,x+1]==0: cv2.floodFill(bl.copy(),m,(x,0),(255,255,255),(7,7,7),(7,7,7),cv2.FLOODFILL_MASK_ONLY|8)
sky=m[1:-1,1:-1]>0
# glass crowns reflect the sky and let the flood fill through: anything textured counts as city too
Vf=V.astype(np.float32); mu=cv2.blur(Vf,(5,5)); sd=np.sqrt(np.maximum(0,cv2.blur(Vf*Vf,(5,5))-mu*mu))
tex=cv2.morphologyEx((sd>5).astype(np.uint8),cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
build=((~sky)|(tex>0)).astype(np.uint8); build[WL:,:]=0
build=cv2.morphologyEx(build,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
n,lab_c=cv2.connectedComponents(build); ground=set(np.unique(lab_c[WL-3:WL,:])); ground.discard(0)
build=np.isin(lab_c,list(ground)).astype(np.uint8)
col_top=np.full(W,WL)
for x in range(W):
    ys=np.where(build[:,x]>0)[0]
    if len(ys): col_top[x]=ys.min()
ct=col_top.copy()
for x in range(1,W-1):
    if col_top[x]<col_top[x-1]-15 and col_top[x]<col_top[x+1]-15: ct[x]=min(col_top[x-1],col_top[x+1])
col_top=ct; TOP=int(col_top.min())
S=600/W; VH=(WL-TOP)*S; Y0=230-VH
def vx(x): return x*S
def vy(y): return Y0+(y-TOP)*S
def fmt(v): s=f'{v:.1f}'; return s[:-2] if s.endswith('.0') else s
sil=build.copy()
# drop sky-coloured pixels riding along the outline
img_f=img.astype(np.float32); skyrow=np.zeros((H,3))
for y in range(H):
    px=img_f[y][build[y]==0]; skyrow[y]=np.median(px,axis=0) if len(px)>40 else (skyrow[y-1] if y else 0)
diff=np.abs(img_f-skyrow[:,None,:]).sum(axis=2)
rim=(sil>0)&(cv2.erode(sil,np.ones((7,7),np.uint8))==0); sil[rim&(diff<45)]=0
sil=cv2.morphologyEx(sil,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
def trace(mask,eps,minarea,mode=cv2.RETR_CCOMP):
    cs,_=cv2.findContours(mask,mode,cv2.CHAIN_APPROX_SIMPLE); d=[]
    for c in cs:
        if cv2.contourArea(c)<minarea: continue
        a=cv2.approxPolyDP(c,eps,True)
        if len(a)<3: continue
        d.append('M'+' '.join(f'{fmt(vx(p[0][0]))} {fmt(vy(p[0][1]))}' for p in a)+'Z')
    return ' '.join(d)
def hexc(bgr): return '#%02x%02x%02x'%(int(bgr[2]),int(bgr[1]),int(bgr[0]))
# flat colours: light smoothing only, so window bands and cladding changes survive
lab=cv2.cvtColor(cv2.GaussianBlur(img,(3,3),0),cv2.COLOR_BGR2LAB)
pix=lab[sil==1].reshape(-1,3).astype(np.float32)
crit=(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,40,.4)
_,labels,centers=cv2.kmeans(pix,K,None,crit,5,cv2.KMEANS_PP_CENTERS)
lab_img=np.full((H,W),-1,np.int32); lab_img[sil==1]=labels.ravel()
lab_u8=cv2.medianBlur((lab_img+1).astype(np.uint8),3); lab_img=lab_u8.astype(int)-1; lab_img[sil==0]=-1
cent=cv2.cvtColor(centers.reshape(1,-1,3).astype(np.uint8),cv2.COLOR_LAB2BGR)[0].astype(float)
haze=np.array([214,200,186]); cent=cent*.86+haze*.14          # a touch of haze, warm-leaning
order=np.argsort(centers[:,0]); layers=[]
for ci in order:
    mask=(lab_img==ci).astype(np.uint8)
    d=trace(mask,EPS,8)
    if d: layers.append(f'<path fill="{hexc(cent[ci])}" d="{d}"/>')
base=hexc(cent[order[1]])
silpath=trace(sil,0.8,20)
# ink: building edges (Canny on the brightness), thinned to one pixel, as a soft dark layer
gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
edges=cv2.Canny(cv2.GaussianBlur(gray,(3,3),0),110,220); edges[sil==0]=0
edges=cv2.morphologyEx(edges,cv2.MORPH_OPEN,np.ones((1,2),np.uint8))|cv2.morphologyEx(edges,cv2.MORPH_OPEN,np.ones((2,1),np.uint8))
ink=trace((edges>0).astype(np.uint8),0.9,3,cv2.RETR_EXTERNAL)
dsky=[]
for k2 in range(61):
    c=k2*10; xs=range(max(0,int((c-5)/S)),min(W,int((c+5)/S)+1))
    dsky.append(str(int(min(vy(col_top[x]) for x in xs))))
svg=(f'<div class="skyline day" aria-hidden="true"><svg viewBox="0 0 600 230" preserveAspectRatio="xMidYMax meet" data-sky="{",".join(dsky)}" aria-hidden="true">'
     f'<path fill="{base}" d="{silpath}"/>'+''.join(layers)+
     f'<path fill="#1d2430" fill-opacity=".28" d="{ink}"/>'
     '</svg></div>')
open(OUT+'/skyline_day.html','w').write(svg)
print('water',WL,'top',TOP,'viewBox h',round(VH,1),'bytes',len(svg),'colours',len(layers),'ink bytes',len(ink))
