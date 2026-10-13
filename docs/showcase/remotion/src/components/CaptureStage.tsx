import React from 'react';
import {Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {C,clamp} from './Design';

export type Point=readonly [number,number];
export const target={
  runExample:[2268,618] as Point,verifyIntegrity:[2040,314] as Point,exportAudit:[2330,314] as Point,
  chainStatus:[432,430] as Point,denyOutcome:[1900,1203] as Point,permitOutcome:[1900,1340] as Point,
  readRow:[940,1330] as Point,detailDone:[1844,236] as Point,detailChain:[900,842] as Point,
  exportsTab:[612,784] as Point,
};
export const between=(f:number,start:number,end:number,a:Point,b:Point):Point=>{
  const t=interpolate(f,[start,end],[0,1],{...clamp,easing:(x)=>1-Math.pow(1-x,3)});
  return [a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
};
const NativeCursor:React.FC<{x:number;y:number;click?:boolean;clickFrame?:number;opacity:number}> = ({x,y,clickFrame,opacity})=>{
  const f=useCurrentFrame();
  const age=clickFrame===undefined?-100:f-clickFrame;
  const ring=age>=0&&age<=26;
  const radius=interpolate(age,[0,26],[12,42],clamp);
  const ringOpacity=interpolate(age,[0,26],[0.58,0],clamp);
  const scale=age>=0&&age<7?interpolate(age,[0,4,7],[1,0.89,1],clamp):1;
  return <div style={{position:'absolute',left:x,top:y,width:0,height:0,opacity,pointerEvents:'none',zIndex:3}}>
    {ring&&<div style={{position:'absolute',left:-radius,top:-radius,width:radius*2,height:radius*2,border:`3px solid ${C.forest}`,borderRadius:'50%',opacity:ringOpacity}}/>}
    <svg width="36" height="43" viewBox="0 0 36 43" style={{position:'absolute',left:0,top:0,filter:'drop-shadow(0 3px 4px #0006)',transform:`scale(${scale})`,transformOrigin:'3px 3px'}} aria-hidden="true">
      <path d="M2 2 L2 33 L10 26 L16 40 L22 37 L16 23 L27 22 Z" fill="#fff" stroke="#14241c" strokeWidth="2.8" strokeLinejoin="round"/>
    </svg>
  </div>;
};
export const CaptureStage:React.FC<{
  source:string;focus?:Point;zoom?:number;opacity?:number;cursor?:Point;cursorOpacity?:number;clickFrame?:number;
  x?:number;y?:number;width?:number;height?:number;
}> = ({source,focus=[1260,792],zoom=1,opacity=1,cursor,cursorOpacity=1,clickFrame,x=640,y=180,width=1190,height=748})=>{
  const base=Math.min(width/2520,height/1584);
  const scale=base*zoom;
  const imgX=width/2-focus[0]*scale;
  const imgY=height/2-focus[1]*scale;
  const cx=cursor?imgX+cursor[0]*scale:0;
  const cy=cursor?imgY+cursor[1]*scale:0;
  return <div style={{position:'absolute',left:x,top:y,width,height,opacity,borderRadius:30,boxShadow:'0 38px 88px rgba(14,44,30,.20), 0 0 0 1px rgba(30,70,49,.20)',background:'#fff',overflow:'hidden'}}>
    <Img src={staticFile(`macos/${source}`)} style={{position:'absolute',left:imgX,top:imgY,width:2520*scale,height:1584*scale,maxWidth:'none'}}/>
    {cursor&&cx>=-10&&cx<=width+10&&cy>=-10&&cy<=height+10&&<NativeCursor x={cx} y={cy} opacity={cursorOpacity} clickFrame={clickFrame}/>}
  </div>;
};
