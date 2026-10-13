import React from 'react';
import {interpolate,useCurrentFrame} from 'remotion';
import {SceneShell,clamp} from '../components/Design';
import {CaptureStage,between,target} from '../components/CaptureStage';
export const InspectRecord:React.FC=()=>{
 const f=useCurrentFrame();
 const detail=interpolate(f,[230,247],[0,1],clamp);
 const cursor=f<265?between(f,85,175,[1450,1000],target.readRow):between(f,300,390,target.readRow,target.detailChain);
 return <SceneShell number={4} tag="03  /  INSPECT" title="Open the record." support="Action, actor, origin and ID. The ledger chain remains Not checked.">
  <CaptureStage source="02-outcomes.png" focus={between(f,0,220,[1260,792],[1190,1100])} zoom={interpolate(f,[0,225],[1,1.33],clamp)} opacity={1-detail} cursor={cursor} cursorOpacity={f<255?interpolate(f,[70,100,230,255],[0,1,1,0],clamp):0} clickFrame={215}/>
  <CaptureStage source="03-detail.png" focus={between(f,280,515,[1260,792],[1130,745])} zoom={interpolate(f,[280,515],[1,1.4],clamp)} opacity={detail} cursor={target.detailChain} cursorOpacity={interpolate(f,[310,365,440,470],[0,1,1,0],clamp)}/>
  <div style={{position:'absolute',left:660,top:122,fontSize:24,fontWeight:750,color:'#245E4D',letterSpacing:1.2}}>SAMPLE ORIGIN: SYNTHETIC_SEED</div>
 </SceneShell>;
};
