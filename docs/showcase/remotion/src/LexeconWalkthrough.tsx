import React from 'react';
import {AbsoluteFill, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {clamp} from './components/Design';

const WINDOW = {x: 320, y: 32, width: 1280, height: 870};
const nativeHeight = WINDOW.width * 1476 / 2174;
const stillHeight = WINDOW.width * 1584 / 2520;
const spring = Easing.spring({damping: 19});
const settle = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {...clamp, easing: spring});

const beats = [
  {at: 0, label: 'LEXECON  /  LOCAL WORKSPACE', text: 'Decisions, with evidence.'},
  {at: 90, label: '01  /  SAMPLE RECORDS', text: 'Two sample records. One denied, one permitted.'},
  {at: 190, label: '02  /  DENIED', text: 'Open a decision. See its actor, source, and outcome.'},
  {at: 505, label: '03  /  PERMITTED', text: 'One read permitted. The chain is still Not checked.'},
  {at: 720, label: '04  /  EVIDENCE', text: 'Verification is a separate step.'},
  {at: 1030, label: '05  /  TIMELINE', text: 'Both sample decisions, in order.'},
  {at: 1320, label: '06  /  ANALYTICS', text: 'Two loaded records. One permit, one deny.'},
  {at: 1610, label: '07  /  EXPORTS', text: 'Evidence ZIP available. No file saved here.'},
  {at: 1780, label: '07  /  EXPORTS', text: 'The route ends before the save dialog.'},
  {at: 1950, label: 'LEXECON', text: 'From policy decision to evidence.'},
];

const movements = [
  {start: 125, end: 187, from: [780, 600], to: [545, 714], until: 190},
  {start: 445, end: 499, from: [610, 702], to: [545, 786], until: 505},
  {start: 930, end: 1024, from: [545, 786], to: [143, 478], until: 1110},
  {start: 1110, end: 1160, from: [143, 478], to: [345, 510], until: 1210},
  {start: 1210, end: 1255, from: [345, 510], to: [345, 590], until: 1275},
  {start: 1275, end: 1314, from: [345, 590], to: [240, 478], until: 1400},
  {start: 1400, end: 1455, from: [240, 478], to: [1000, 622], until: 1545},
  {start: 1545, end: 1603, from: [1000, 622], to: [325, 478], until: 1700},
  {start: 1700, end: 1755, from: [325, 478], to: [115, 600], until: 1880},
] as const;

const cursorAt = (frame: number): readonly [number, number] | null => {
  const move = movements.find(({start, until}) => frame >= start && frame < until);
  if (!move) return null;
  const progress = interpolate(frame, [move.start, move.end], [0, 1], {
    ...clamp, easing: Easing.bezier(.22, .78, .24, 1),
  });
  const [fromX, fromY] = move.from;
  const [toX, toY] = move.to;
  const lift = Math.min(56, Math.hypot(toX - fromX, toY - fromY) * .13);
  const u = 1 - progress;
  return [
    u * u * u * fromX + 3 * u * u * progress * (fromX + (toX - fromX) * .34) +
      3 * u * progress * progress * (fromX + (toX - fromX) * .73) + progress ** 3 * toX,
    u * u * u * fromY + 3 * u * u * progress * (fromY - lift) +
      3 * u * progress * progress * (toY - lift) + progress ** 3 * toY,
  ];
};

const Cursor: React.FC<{frame: number}> = ({frame}) => {
  const current = cursorAt(frame);
  if (!current) return null;
  const previous = cursorAt(frame - 1) ?? current;
  const [x, y] = current;
  const vx = x - previous[0];
  const vy = y - previous[1];
  const speed = Math.hypot(vx, vy);
  const length = Math.min(30, speed * 2.4);
  const angle = Math.atan2(vy, vx);
  const activeStart = frame >= 930 ? 930 : frame < 190 ? 125 : 445;
  const activeEnd = frame >= 930 ? 1880 : frame < 190 ? 190 : 505;
  const visible = Math.max(0, Math.min(1, (frame - activeStart) / 10, (activeEnd - frame) / 10));
  const click = [1030, 1320, 1610].find((at) => frame >= at && frame < at + 14);
  return <div style={{position: 'absolute', inset: 0, opacity: visible, pointerEvents: 'none'}}>
    {speed > 1.3 && <div style={{position: 'absolute', left: x - Math.cos(angle) * length, top: y - Math.sin(angle) * length,
      width: length, height: 5, borderRadius: 5, transform: `rotate(${angle}rad)`, transformOrigin: 'left center',
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.56))', filter: 'blur(2.4px)', opacity: Math.min(.6, speed / 22)}}/>}
    {click !== undefined && <div style={{position: 'absolute', left: x - 18, top: y - 18, width: 36, height: 36,
      border: '2px solid #2D765F', borderRadius: '50%', opacity: .35 * (1 - (frame - click) / 14),
      transform: `scale(${.55 + (frame - click) / 14 * .7})`}}/>}
    <svg width="34" height="41" viewBox="0 0 36 43" aria-hidden="true" style={{position: 'absolute', left: x, top: y,
      filter: `blur(${Math.min(.55, speed * .04)}px) drop-shadow(0 2px 3px rgba(0,0,0,.5))`}}>
      <path d="M2 2 L2 33 L10 26 L16 40 L22 37 L16 23 L27 22 Z" fill="white" stroke="#14241C" strokeWidth="2.8" strokeLinejoin="round"/>
    </svg>
  </div>;
};

const Backdrop: React.FC = () => <AbsoluteFill style={{background: [
  'radial-gradient(ellipse 64% 88% at 83% 109%, rgba(255,229,174,.96) 0%, rgba(252,172,129,.78) 26%, rgba(225,115,147,.3) 58%, transparent 78%)',
  'radial-gradient(ellipse 65% 82% at 72% 2%, rgba(131,84,165,.71) 0%, transparent 79%)',
  'radial-gradient(ellipse 69% 74% at 3% 104%, rgba(75,45,110,.72) 0%, transparent 80%)',
  'linear-gradient(135deg, #171940 0%, #352960 36%, #86517C 68%, #E28888 100%)',
].join(', ')}}/>;

const Captions: React.FC<{frame: number}> = ({frame}) => {
  const beat = [...beats].reverse().find(({at}) => frame >= at)!;
  const nudge = interpolate(settle(frame, beat.at, 18), [0, 1], [14, 0], clamp);
  return <div style={{position: 'absolute', left: WINDOW.x, top: 923, width: WINDOW.width,
    fontFamily: 'Avenir Next, Helvetica Neue, Arial, sans-serif', color: '#FFF9FA'}}>
    <div style={{fontSize: 16, fontWeight: 700, letterSpacing: 3.2, color: '#FFE1D6'}}>{beat.label}</div>
    <div style={{marginTop: 8, fontSize: frame < 90 ? 42 : 29, lineHeight: 1.1, fontWeight: 600,
      letterSpacing: frame < 90 ? -2.2 : -1, transform: `translateY(${nudge}px)`}}>{beat.text}</div>
    {((frame >= 190 && frame < 430) || (frame >= 505 && frame < 690) || frame >= 1030) && <div style={{marginTop: 15, fontSize: 14, fontWeight: 700, letterSpacing: 2.1, color: '#F7D8E3'}}>
      ILLUSTRATIVE DEMO  ·  SAMPLE RECORDS  ·  NO API CONNECTION
    </div>}
  </div>;
};

const tabs = [
  {name: 'Ledger', x: 38, width: 52},
  {name: 'Timeline', x: 118, width: 62},
  {name: 'Analytics', x: 210, width: 72},
  {name: 'Exports', x: 304, width: 65},
] as const;
const tabScenes = [
  {at: 1030, name: 'Timeline', src: '04-timeline.png'},
  {at: 1320, name: 'Analytics', src: '05-analytics.png'},
  {at: 1610, name: 'Exports', src: '06-exports.png'},
] as const;

const TabNav: React.FC<{frame: number; active: string; previous: string; start: number}> = ({frame, active, previous, start}) => {
  const from = tabs.find((tab) => tab.name === previous)!;
  const to = tabs.find((tab) => tab.name === active)!;
  const progress = settle(frame, start, 18);
  const underlineX = interpolate(progress, [0, 1], [from.x, to.x], clamp);
  const underlineWidth = interpolate(progress, [0, 1], [from.width, to.width], clamp);
  return <div style={{position: 'absolute', top: 450, left: 0, width: WINDOW.width, height: 65,
    background: '#F2F4EF', borderBottom: '1px solid #D9DFD9', fontFamily: 'Arial, sans-serif'}}>
    {tabs.map((tab) => <div key={tab.name} style={{position: 'absolute', left: tab.x, top: 17, width: tab.width,
      fontSize: 15, fontWeight: tab.name === active ? 700 : 600,
      color: tab.name === active ? '#2B6855' : '#858A85'}}>{tab.name}</div>)}
    <div style={{position: 'absolute', left: underlineX, width: underlineWidth, bottom: 0, height: 2, background: '#2B6855'}}/>
  </div>;
};

const TabBody: React.FC<{frame: number; sceneIndex: number}> = ({frame, sceneIndex}) => {
  const scene = tabScenes[sceneIndex];
  const rise = interpolate(settle(frame, scene.at, 18), [0, 1], [12, 0], clamp);
  return <div style={{position: 'absolute', top: 515, bottom: 0, left: 0, width: WINDOW.width,
    overflow: 'hidden', background: '#F2F4EF'}}>
    <Img src={staticFile(`macos/${scene.src}`)} style={{position: 'absolute', left: 0, top: -430 + rise,
      width: WINDOW.width, height: stillHeight}}/>
  </div>;
};

const NativeWindow: React.FC<{frame: number}> = ({frame}) => {
  const entry = interpolate(settle(frame, 0, 28), [0, 1], [10, 0], clamp);
  const sceneIndex = frame >= 1610 ? 2 : frame >= 1320 ? 1 : frame >= 1030 ? 0 : -1;
  const scene = sceneIndex < 0 ? null : tabScenes[sceneIndex as 0 | 1 | 2];
  const previousName = sceneIndex === 0 ? 'Ledger' : sceneIndex > 0 ? tabScenes[sceneIndex - 1].name : 'Ledger';
  return <div style={{position: 'absolute', left: WINDOW.x, top: WINDOW.y, width: WINDOW.width,
    height: WINDOW.height, overflow: 'hidden', borderRadius: 24, transform: `translateY(${entry}px)`,
    boxShadow: '0 44px 85px rgba(19,16,45,.36), 0 12px 28px rgba(19,16,45,.18)', background: '#F2F4EF'}}>
    {frame < 90 && <Img src={staticFile('native/ledger-start.png')} style={{position: 'absolute', left: 0, top: 0, width: WINDOW.width, height: nativeHeight}}/>}
    <Sequence from={90} durationInFrames={750}>
      <OffthreadVideo src={staticFile('native/offline-ledger.mov')} muted style={{position: 'absolute', left: 0, top: 0,
        width: WINDOW.width, height: nativeHeight}}/>
    </Sequence>
    {frame >= 840 && <Img src={staticFile('native/ledger-rest.png')} style={{position: 'absolute', left: 0, top: 0,
      width: WINDOW.width, height: nativeHeight}}/>}
    {scene && <>
      <TabNav frame={frame} active={scene.name} previous={previousName} start={scene.at}/>
      <TabBody frame={frame} sceneIndex={sceneIndex}/>
    </>}
    <Cursor frame={frame}/>
  </div>;
};

export const LexeconWalkthrough: React.FC = () => {
  const frame = useCurrentFrame();
  return <AbsoluteFill>
    <Backdrop/>
    <NativeWindow frame={frame}/>
    <Captions frame={frame}/>
  </AbsoluteFill>;
};
