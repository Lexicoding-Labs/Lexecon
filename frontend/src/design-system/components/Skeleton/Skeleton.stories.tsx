import type { Meta, StoryObj } from '@storybook/react';
import { Skeleton, TableSkeleton, CardSkeleton, PageSkeleton } from './Skeleton';

const meta: Meta<typeof Skeleton> = {
  title: 'Design System / Skeleton',
  component: Skeleton,
};
export default meta;

export const Single: StoryObj = {
  name: 'Single Line',
  render: () => <Skeleton width="200px" height={16} />,
};

export const TableSkeletonStory: StoryObj = {
  name: 'Table Skeleton',
  render: () => (
    <div style={{ border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
      <TableSkeleton rows={6} columns={7} />
    </div>
  ),
};

export const CardSkeletonStory: StoryObj = {
  name: 'Card Skeleton (4-up)',
  render: () => <CardSkeleton count={4} />,
};

export const PageSkeletonStory: StoryObj = {
  name: 'Full Page Skeleton',
  render: () => <PageSkeleton />,
};
