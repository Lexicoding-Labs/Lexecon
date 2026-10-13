import React from 'react';
import {Composition, Folder} from 'remotion';
import {LexeconWalkthrough} from './LexeconWalkthrough';
import {LexeconWalkthrough as LegacyWalkthrough} from './LegacyWalkthrough';
import {Opening} from './scenes/Opening';
import {PolicySurface} from './scenes/PolicySurface';
import {SampleOutcomes} from './scenes/SampleOutcomes';
import {InspectRecord} from './scenes/InspectRecord';
import {IntegrityBoundary} from './scenes/IntegrityBoundary';
import {ExportRoute} from './scenes/ExportRoute';
import {Closing} from './scenes/Closing';

export const Root: React.FC = () => <>
  <Composition id="LexeconWalkthrough" component={LexeconWalkthrough} width={1920} height={1080} fps={60} durationInFrames={2100}/>
  <Composition id="LexeconLegacy54" component={LegacyWalkthrough} width={1920} height={1080} fps={60} durationInFrames={3240}/>
  <Folder name="Legacy-54s-Scenes">
    <Composition id="Opening" component={Opening} width={1920} height={1080} fps={60} durationInFrames={300}/>
    <Composition id="PolicySurface" component={PolicySurface} width={1920} height={1080} fps={60} durationInFrames={540}/>
    <Composition id="SampleOutcomes" component={SampleOutcomes} width={1920} height={1080} fps={60} durationInFrames={600}/>
    <Composition id="InspectRecord" component={InspectRecord} width={1920} height={1080} fps={60} durationInFrames={600}/>
    <Composition id="IntegrityBoundary" component={IntegrityBoundary} width={1920} height={1080} fps={60} durationInFrames={540}/>
    <Composition id="ExportRoute" component={ExportRoute} width={1920} height={1080} fps={60} durationInFrames={480}/>
    <Composition id="Closing" component={Closing} width={1920} height={1080} fps={60} durationInFrames={360}/>
  </Folder>
</>;
