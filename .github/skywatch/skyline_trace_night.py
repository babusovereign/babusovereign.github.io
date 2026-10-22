"""Writes skyline_night.html with inline fills (night has no theme variants)."""
import cv2, numpy as np
SRC='/root/.claude/uploads/9f38b2cf-1489-5540-bb84-653f7bd5277e/ee1c13db-image.png'
OUT='/tmp/claude-0/-home-claude/9f38b2cf-1489-5540-bb84-653f7bd5277e/scratchpad'
img=cv2.imread(SRC); H0,W0=img.shape[:2]
# crop the Bay Bridge tower at the left (it spans the first ~10% of the frame) and find the water line: the lit shoreline is
# the row with the most very bright pixels in the lower part of the frame; the water starts just under it
x0=175
img=img[:,x0:]; H,W=img.shape[:2]
V=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)[:,:,2]
rb=(V>200).sum(axis=1); lo=int(H*.75)
WL=int(np.argmax(rb[lo:])+lo)+7
# sky vs city: the sky is smooth, the city is textured (windows, edges). Local standard deviation of brightness marks the city;
# closing fills the building interiors, an opening drops stray specks
Vf=V.astype(np.float32); mu=cv2.blur(Vf,(7,7)); sd=np.sqrt(np.maximum(0,cv2.blur(Vf*Vf,(7,7))-mu*mu))
tex=(sd>7).astype(np.uint8); tex[WL:,:]=0
build=cv2.morphologyEx(tex,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
build=cv2.morphologyEx(build,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
build=cv2.morphologyEx(build,cv2.MORPH_OPEN,np.ones((13,1),np.uint8))   # drops the thin horizontal fog band lying across the rooftops; towers are taller than that
# keep only components that touch the ground (the water line); clouds and stars do not
n,lab_c=cv2.connectedComponents(build)
ground=set(np.unique(lab_c[WL-3:WL,:])); ground.discard(0)
build=np.isin(lab_c,list(ground)).astype(np.uint8)
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
sil=cv2.erode(build,np.ones((3,3),np.uint8)); sil[WL-4:WL,:]=build[WL-4:WL,:]
# sky-coloured pixels that rode into the mask at the roof edges (the haze right behind the rooftops): compare each
# city pixel with the sky's colour on its own row and drop the ones that match
skyrow=np.zeros((H,3)); img_f=img.astype(np.float32)
for y in range(H):
    px=img_f[y][build[y]==0]
    skyrow[y]=np.median(px,axis=0) if len(px)>40 else (skyrow[y-1] if y else 0)
diff=np.abs(img_f-skyrow[:,None,:]).sum(axis=2)
rim=(sil>0)&(cv2.erode(sil,np.ones((9,9),np.uint8))==0)   # only the outer few pixels along the outline
sil[rim&(diff<110)&(V<170)]=0
sil=cv2.morphologyEx(sil,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))   # the city itself, pulled in a little so no sky halo rides along the roofs
def trace(mask,eps,minarea):
    cs,_=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE); d=[]
    for c in cs:
        if cv2.contourArea(c)<minarea: continue
        a=cv2.approxPolyDP(c,eps,True)
        if len(a)<3: continue
        d.append('M'+' '.join(f'{fmt(vx(p[0][0]))} {fmt(vy(p[0][1]))}' for p in a)+'Z')
    return ' '.join(d)
def hexc(bgr): return '#%02x%02x%02x'%(int(bgr[2]),int(bgr[1]),int(bgr[0]))
silpath=trace(sil,1.0,30)
# dark masses: quantise the unlit pixels into 5 flat colours
lab=cv2.cvtColor(cv2.GaussianBlur(img,(3,3),0),cv2.COLOR_BGR2LAB)
rim2=(sil>0)&(cv2.erode(sil,np.ones((7,7),np.uint8))==0)
lit=(((V>135)&~rim2)|(V>205))&(sil==1)   # along the outline only the real lights count, not the haze behind the roofs
dark_pix=(sil==1)&~lit
pix=lab[dark_pix].reshape(-1,3).astype(np.float32)
crit=(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,30,.5)
_,labels,centers=cv2.kmeans(pix,5,None,crit,4,cv2.KMEANS_PP_CENTERS)
lab_img=np.full((H,W),-1,np.int32); lab_img[dark_pix]=labels.ravel()
lab_u8=cv2.medianBlur((lab_img+1).astype(np.uint8),5); lab_img=lab_u8.astype(int)-1; lab_img[~dark_pix]=-1
cent=cv2.cvtColor(centers.reshape(1,-1,3).astype(np.uint8),cv2.COLOR_LAB2BGR)[0].astype(int)
cent=(cent*.55+np.array([58,38,22])*.45).astype(int)   # toward slate (BGR)
hsvc=cv2.cvtColor(cent.reshape(1,-1,3).astype(np.uint8),cv2.COLOR_BGR2HSV); hsvc[...,1]=np.minimum(hsvc[...,1],70)   # unlit stone and glass at night is near-grey
cent=cv2.cvtColor(hsvc,cv2.COLOR_HSV2BGR)[0].astype(int)
order=np.argsort(centers[:,0]); layers=[]
for i,ci in enumerate(order):
    mask=(lab_img==ci).astype(np.uint8); mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
    d=trace(mask,1.6,40)
    if d: layers.append(f'<path fill="{hexc(cent[ci])}" d="{d}"/>')
base=hexc(cent[order[1]])
# lights: bright pixels, split into 4 colours (amber, warm white, cool white, blue) and traced finely so windows stay separate
lp=lab[lit].reshape(-1,3).astype(np.float32)
_,ll,lc=cv2.kmeans(lp,4,None,crit,4,cv2.KMEANS_PP_CENTERS)
lmap=np.full((H,W),-1,np.int32); lmap[lit]=ll.ravel()
lcent=cv2.cvtColor(lc.reshape(1,-1,3).astype(np.uint8),cv2.COLOR_LAB2BGR)[0].astype(int)
lights=[]; nlights=0
for ci in range(4):
    mask=(lmap==ci).astype(np.uint8)
    cs,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE); d=[]
    for c in cs:
        a=cv2.contourArea(c)
        if a<3: continue
        x,y,w,h=cv2.boundingRect(c)
        if a<24:   # a window: one small rect
            d.append(f'M{fmt(vx(x))} {fmt(vy(y))}h{fmt(max(.5,w*S))}v{fmt(max(.5,h*S))}h-{fmt(max(.5,w*S))}z')
        else:
            ap2=cv2.approxPolyDP(c,1.2,True)
            if len(ap2)<3: continue
            d.append('M'+' '.join(f'{fmt(vx(p[0][0]))} {fmt(vy(p[0][1]))}' for p in ap2)+'Z')
        nlights+=1
    if d: lights.append(f'<path class="lt" fill="{hexc(np.minimum(255,lcent[ci]*1.08))}" d="{" ".join(d)}"/>')
dsky=[]
for k2 in range(61):
    c=k2*10; xs=range(max(0,int((c-5)/S)),min(W,int((c+5)/S)+1))
    dsky.append(str(int(min(vy(col_top[x]) for x in xs))))
bx=int(np.argmin(col_top)); beacon=(vx(bx),vy(col_top[bx])-2)
svg=(f'<div class="skyline night" aria-hidden="true"><svg viewBox="0 0 600 230" preserveAspectRatio="xMidYMax meet" data-sky="{",".join(dsky)}" aria-hidden="true">'
     f'<path fill="{base}" d="{silpath}"/>'+''.join(layers)+''.join(lights)+
     f'<circle class="beacon" cx="{beacon[0]:.1f}" cy="{beacon[1]:.1f}" r="1.6"/>'
     '</svg></div>')
open(OUT+'/skyline_night.html','w').write(svg)
cv2.imwrite(OUT+'/night_crop.png',img)
print('crop x0',x0,'water',WL,'top',TOP,'viewBox h',round(VH,1),'bytes',len(svg),'lights',nlights,'light colours',[hexc(c) for c in lcent])
