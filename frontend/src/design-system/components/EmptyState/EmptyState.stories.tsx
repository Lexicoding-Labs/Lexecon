import type { Meta, StoryObj } from '@storybook/react';
import { EmptyState } from './EmptyState';

const meta: Meta<typeof EmptyState> = {
  title: 'Design System / EmptyState',
  component: EmptyState,
};
export default meta;

export const Default: StoryObj = {
  args: {
    icon: '📭',
    title: 'No results found',
    description: 'Try adjusting your filters or search terms.',
  },
};

export const WithActions: StoryObj = {
  name: 'With Actions',
  args: {
    icon: '📊',
    title: 'No decisions yet',
    description: 'Your ledger is empty. Load demo data to get started.',
    actions: [
      { label: 'Load Demo Data', onClick: () => console.log('load') },
      { label: 'Learn More', onClick: () => console.log('learn'), variant: 'secondary' },
    ],
  },
};

export const MinimalNoIcon: StoryObj = {
  name: 'Minimal – No Icon',
  args: {
    title: 'Nothing to see here',
    description: 'All clear.',
  },
};
