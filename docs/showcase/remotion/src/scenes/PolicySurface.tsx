import React from 'react';
import {useCurrentFrame,interpolate} from 'remotion';
import {SceneShell,clamp} from '../components/Design';
import {CaptureStage,between,target} from '../components/CaptureStage';
export const PolicySurface:React.FC=()=>{
 const f=useCurrentFrame();
 const cursor=between(f,72,160,[1450,850],target.runExample);
 return <SceneShell number={2} tag="01  /  THE CONTROL" title="Start with a policy." support="The example control requests a read and a delete. No external tool executes.">
   <CaptureStage source="01-empty.png" focus={[1260,792]} zoom={interpolate(f,[0,360],[1,1.04],clamp)} cursor={cursor} cursorOpacity={interpolate(f,[55,85,300,330],[0,1,1,0],clamp)}/>
   <div style={{position:'absolute',left:658,top:124,fontSize:25,fontWeight:700,color:'#245E4D',letterSpacing:1.2}}>THE CONTROL IS SHOWN · NO RUN WAS CAPTURED</div>
 </SceneShell>;
};
