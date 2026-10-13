import React from 'react';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {wipe} from '@remotion/transitions/wipe';
import {Opening} from './scenes/Opening';
import {PolicySurface} from './scenes/PolicySurface';
import {SampleOutcomes} from './scenes/SampleOutcomes';
import {InspectRecord} from './scenes/InspectRecord';
import {IntegrityBoundary} from './scenes/IntegrityBoundary';
import {ExportRoute} from './scenes/ExportRoute';
import {Closing} from './scenes/Closing';

export const LexeconWalkthrough: React.FC = () => <TransitionSeries>
  <TransitionSeries.Sequence durationInFrames={300}><Opening/></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 30})}/>
  <TransitionSeries.Sequence durationInFrames={540}><PolicySurface/></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={wipe({direction:'from-right'})} timing={linearTiming({durationInFrames: 30})}/>
  <TransitionSeries.Sequence durationInFrames={600}><SampleOutcomes/></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={wipe({direction:'from-right'})} timing={linearTiming({durationInFrames: 30})}/>
  <TransitionSeries.Sequence durationInFrames={600}><InspectRecord/></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={wipe({direction:'from-right'})} timing={linearTiming({durationInFrames: 30})}/>
  <TransitionSeries.Sequence durationInFrames={540}><IntegrityBoundary/></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={wipe({direction:'from-right'})} timing={linearTiming({durationInFrames: 30})}/>
  <TransitionSeries.Sequence durationInFrames={480}><ExportRoute/></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 30})}/>
  <TransitionSeries.Sequence durationInFrames={360}><Closing/></TransitionSeries.Sequence>
</TransitionSeries>;
