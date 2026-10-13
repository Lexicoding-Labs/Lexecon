import React from 'react';
import {interpolate,useCurrentFrame} from 'remotion';
import {SceneShell,clamp} from '../components/Design';
import {CaptureStage,between,target} from '../components/CaptureStage';
export const ExportRoute:React.FC=()=>{
 const f=useCurrentFrame();
 const switched=interpolate(f,[170,215],[0,1],clamp);
 const cursor=between(f,60,145,[1100,780],target.exportsTab);
 return <SceneShell number={6} tag="05  /  EXPORTS" title="A route for the evidence." support="The Exports view describes a ZIP workflow. No file was saved in this capture.">
  <CaptureStage source="02-outcomes.png" opacity={1-switched} cursor={cursor} cursorOpacity={interpolate(f,[45,75,150,180],[0,1,1,0],clamp)} clickFrame={165}/>
  <CaptureStage source="06-exports.png" opacity={switched} focus={between(f,210,395,[1260,792],[1120,910])} zoom={interpolate(f,[210,395],[1,1.22],clamp)}/>
  <div style={{position:'absolute',left:660,top:122,fontSize:24,fontWeight:750,color:'#245E4D',letterSpacing:1.2}}>EXPORTS TAB · NO ZIP SAVED</div>
 </SceneShell>;
};
