/* Light / dark switch — shared by /, /builds/ and /ledger/.
   The tiny boot script that sets data-theme before first paint (and re-applies
   it on bfcache pageshow / cross-tab storage) stays inline in each page's <head>.
   This file only wires the .themetoggle button and keeps its label in sync. */
(function(){var b=document.querySelector('.themetoggle');if(!b)return;var mq=window.matchMedia&&matchMedia('(prefers-color-scheme: dark)');
  function isDark(){var t=document.documentElement.getAttribute('data-theme');return t?t==='dark':!!(mq&&mq.matches)}
  function label(){var t=isDark()?'Switch to light mode':'Switch to dark mode';b.setAttribute('aria-label',t);b.title=t}
  b.addEventListener('click',function(){var n=isDark()?'light':'dark';document.documentElement.setAttribute('data-theme',n);try{localStorage.setItem('theme',n)}catch(e){}label()});
  if(mq&&mq.addEventListener)mq.addEventListener('change',label);
  /* data-theme can also change outside a click (head boot script on pageshow / storage) — keep the label in sync */
  if(window.MutationObserver)new MutationObserver(label).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  label()})();
