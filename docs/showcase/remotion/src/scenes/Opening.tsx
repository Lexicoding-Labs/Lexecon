import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {Backdrop,C,Eyebrow,Provenance,Reveal,clamp} from '../components/Design';
import {CaptureStage} from '../components/CaptureStage';
export const Opening:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{fontFamily:'-apple-system, BlinkMacSystemFont, Arial, sans-serif',color:C.cream}}>
  <Backdrop dark/>
  <div style={{position:'absolute',left:108,top:104}}><Reveal from={3}><Eyebrow dark>NATIVE MAC WORKSPACE  /  LOCAL PROTOTYPE</Eyebrow></Reveal></div>
  <div style={{position:'absolute',left:104,top:230,width:950,zIndex:2}}>
    <Reveal from={8}><div style={{fontSize:150,fontWeight:740,lineHeight:1,letterSpacing:-9}}>Lexecon.</div></Reveal>
    <Reveal from={25} style={{marginTop:40}}><div style={{fontSize:88,fontWeight:650,lineHeight:1.05,letterSpacing:-5}}>Decisions,<br/>with evidence.</div></Reveal>
    <Reveal from={62} style={{marginTop:38}}><div style={{fontSize:42,color:C.sage}}>A view into the local policy workspace.</div></Reveal>
  </div>
  <div style={{opacity:interpolate(f,[20,75,240,290],[0,.56,.56,.38],clamp),transform:`translateY(${interpolate(f,[20,90],[70,0],clamp)}px)`,filter:'saturate(.65)'}}>
    <CaptureStage source="01-empty.png" x={1130} y={270} width={720} height={453} zoom={1.05}/>
  </div>
  <Provenance dark/>
 </AbsoluteFill>;
};
