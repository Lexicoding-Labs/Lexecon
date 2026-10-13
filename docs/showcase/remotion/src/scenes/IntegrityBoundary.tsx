import React from 'react';
import {interpolate,useCurrentFrame} from 'remotion';
import {SceneShell,clamp} from '../components/Design';
import {CaptureStage,between,target} from '../components/CaptureStage';
export const IntegrityBoundary:React.FC=()=>{
 const f=useCurrentFrame();
 const cursor=between(f,80,165,[1350,500],target.verifyIntegrity);
 return <SceneShell number={5} tag="04  /  VERIFY" title="Integrity is a separate check." support="The control is visible. These sample records remain Not checked.">
  <CaptureStage source="02-outcomes.png" focus={between(f,0,360,[1260,792],[1260,500])} zoom={interpolate(f,[0,360],[1,1.25],clamp)} cursor={cursor} cursorOpacity={interpolate(f,[65,95,225,255],[0,1,1,0],clamp)}/>
  <div style={{position:'absolute',left:660,top:122,fontSize:24,fontWeight:750,color:'#245E4D',letterSpacing:1.2}}>NO VERIFICATION WAS RUN IN THIS CAPTURE</div>
 </SceneShell>;
};
