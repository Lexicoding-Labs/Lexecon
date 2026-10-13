import type { Meta, StoryObj } from '@storybook/react';
import { Badge } from './Badge';

const meta: Meta<typeof Badge> = {
  component: Badge,
  title: 'Design System / Badge',
  argTypes: {
    variant: { control: 'select', options: ['default','primary','success','warning','error','info'] },
    size: { control: 'select', options: ['sm','md','lg'] },
    dot: { control: 'boolean' },
    pulseDot: { control: 'boolean' },
  },
};
export default meta;
type Story = StoryObj<typeof Badge>;

export const Default: Story = {
  args: { children: 'Default', variant: 'default', size: 'md' },
};

export const AllVariants: Story = {
  name: 'All Variants',
  render: () => (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {(['default','primary','success','warning','error','info'] as const).map((v) => (
        <Badge key={v} variant={v} size="md">{v}</Badge>
      ))}
    </div>
  ),
};

export const WithPulseDot: Story = {
  name: 'Pulse Dot – Live Status',
  render: () => (
    <div style={{ display: 'flex', gap: 12 }}>
      <Badge variant="success" pulseDot>Online</Badge>
      <Badge variant="warning" pulseDot>Degraded</Badge>
      <Badge variant="error" pulseDot>Outage</Badge>
    </div>
  ),
};

export const Sizes: Story = {
  name: 'Sizes',
  render: () => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <Badge variant="primary" size="sm">Small</Badge>
      <Badge variant="primary" size="md">Medium</Badge>
      <Badge variant="primary" size="lg">Large</Badge>
    </div>
  ),
};
