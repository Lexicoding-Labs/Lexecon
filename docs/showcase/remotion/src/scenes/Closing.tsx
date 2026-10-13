import React from 'react';
import {AbsoluteFill,interpolate,useCurrentFrame} from 'remotion';
import {Backdrop,C,Eyebrow,Provenance,Reveal,clamp} from '../components/Design';
import {CaptureStage} from '../components/CaptureStage';
export const Closing:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{fontFamily:'-apple-system, BlinkMacSystemFont, Arial, sans-serif',color:C.cream}}>
  <Backdrop dark/>
  <div style={{position:'absolute',left:106,top:105}}><Reveal from={3}><Eyebrow dark>LEXECON  /  LOCAL WORKSPACE</Eyebrow></Reveal></div>
  <div style={{position:'absolute',left:105,top:300,zIndex:2}}>
    <Reveal from={12}><div style={{fontSize:139,fontWeight:760,letterSpacing:-8,lineHeight:1}}>Lexecon.</div></Reveal>
    <Reveal from={29} style={{marginTop:42}}><div style={{fontSize:86,fontWeight:600,lineHeight:1.16,letterSpacing:-4}}>Decisions, with evidence.</div></Reveal>
    <Reveal from={56} style={{marginTop:51}}><div style={{fontSize:40,color:C.sage}}>Policy → decision → evidence.</div></Reveal>
    <Reveal from={70} style={{marginTop:24}}><div style={{fontSize:29,color:'#ACCCB7'}}>Illustrative Mac walkthrough · local single-organization prototype</div></Reveal>
  </div>
  <div style={{opacity:interpolate(f,[0,90,230,300],[.4,.2,.2,.13],clamp)}}><CaptureStage source="06-exports.png" x={1250} y={300} width={570} height={358} zoom={1}/></div>
  <Provenance dark/>
 </AbsoluteFill>;
};
