import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';

export const C={ink:'#111D19',forest:'#245E4D',cream:'#F3F5EF',sage:'#C9DED2',muted:'#52665C',white:'#FFFFFF'};
export const ease=Easing.bezier(0.16,1,0.3,1);
export const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};

export const Backdrop:React.FC<{dark?:boolean}> = ({dark=false})=>{
  const f=useCurrentFrame();
  const glowX=interpolate(f,[0,600],[72,28],clamp);
  const glowY=interpolate(f,[0,600],[24,72],clamp);
  return <AbsoluteFill style={{background:dark?`radial-gradient(circle at ${glowX}% ${glowY}%, #2E6654 0, #1A382E 42%, ${C.ink} 87%)`:`radial-gradient(circle at ${glowX}% ${glowY}%, #E4EDE3 0, ${C.cream} 48%, #E9F0E8 100%)`}}/>;
};
export const Reveal:React.FC<{children:React.ReactNode;from?:number;style?:React.CSSProperties}> = ({children,from=0,style={}})=>{
  const f=useCurrentFrame();
  return <div style={{overflow:'hidden',...style}}><div style={{opacity:interpolate(f,[from,from+14],[0,1],clamp),transform:`translateY(${interpolate(f,[from,from+18],[36,0],{...clamp,easing:ease})}px)`}}>{children}</div></div>;
};
export const Eyebrow:React.FC<{children:React.ReactNode;dark?:boolean}> = ({children,dark=false})=><div style={{fontSize:24,fontWeight:750,letterSpacing:3.5,color:dark?C.sage:C.forest,textTransform:'uppercase',fontFamily:'SFMono-Regular, Menlo, monospace'}}>{children}</div>;
export const Provenance:React.FC<{dark?:boolean}> = ({dark=false})=><div style={{position:'absolute',left:96,bottom:42,fontSize:22,letterSpacing:1.4,fontWeight:700,color:dark?C.sage:C.forest,fontFamily:'SFMono-Regular, Menlo, monospace'}}>ILLUSTRATIVE DEMO  ·  SAMPLE RECORDS  ·  NO API CONNECTION</div>;
export const Progress:React.FC<{scene:number;dark?:boolean}> = ({scene,dark=false})=><div style={{position:'absolute',right:96,bottom:42,display:'flex',alignItems:'center',gap:15,color:dark?C.sage:C.muted,fontSize:20,fontWeight:700,fontFamily:'SFMono-Regular, Menlo, monospace'}}><span>{String(scene).padStart(2,'0')} / 07</span><span style={{width:68,height:3,background:dark?C.sage:C.forest,borderRadius:3}}/></div>;
export const SceneShell:React.FC<{number:number;title:string;support:string;children:React.ReactNode;tag?:string}> = ({number,title,support,children,tag})=><AbsoluteFill style={{fontFamily:'-apple-system, BlinkMacSystemFont, SF Pro Display, Arial, sans-serif',color:C.ink}}>
  <Backdrop/>
  <div style={{position:'absolute',left:96,top:82,width:520}}>
    <Reveal from={2}><Eyebrow>{tag??'LEXECON / LOCAL WORKSPACE'}</Eyebrow></Reveal>
    <Reveal from={10} style={{marginTop:46}}><div style={{fontSize:76,lineHeight:1.04,fontWeight:730,letterSpacing:-4}}>{title}</div></Reveal>
    <Reveal from={24} style={{marginTop:36}}><div style={{fontSize:42,lineHeight:1.25,fontWeight:450,color:C.muted,letterSpacing:-1.2}}>{support}</div></Reveal>
  </div>
  {children}
  <Provenance/><Progress scene={number}/>
</AbsoluteFill>;
