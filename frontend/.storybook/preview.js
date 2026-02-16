import '../src/styles/global.css';

export const decorators = [
  (Story) => {
    // Toggle dark class via globals
    return <Story />;
  },
];

export const globals = {
  theme: 'light',
};

export const parameters = {
  backgrounds: {
    default: 'light',
    values: [
      { name: 'light', value: '#FFFFFF' },
      { name: 'dark', value: '#0A0A0A' },
    ],
  },
};
