import React from 'react';
import {interpolate,useCurrentFrame} from 'remotion';
import {SceneShell,clamp} from '../components/Design';
import {CaptureStage,between,target} from '../components/CaptureStage';
export const SampleOutcomes:React.FC=()=>{
 const f=useCurrentFrame();
 const cursor=f<300?between(f,95,200,[1550,980],target.denyOutcome):between(f,310,390,target.denyOutcome,target.permitOutcome);
 return <SceneShell number={3} tag="02  /  SAMPLE RECORDS" title="Two outcomes. One view." support="Illustrative read and delete records. Their origin is synthetic_seed.">
  <CaptureStage source="02-outcomes.png" focus={between(f,110,360,[1260,792],[1400,1100])} zoom={interpolate(f,[110,360],[1,1.49],clamp)} cursor={cursor} cursorOpacity={interpolate(f,[75,105,440,465],[0,1,1,0],clamp)}/>
  <div style={{position:'absolute',left:660,top:122,fontSize:24,fontWeight:750,color:'#245E4D',letterSpacing:1.2}}>READ → PERMIT   /   DELETE → DENY</div>
 </SceneShell>;
};
