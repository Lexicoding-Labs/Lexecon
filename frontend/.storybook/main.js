module.exports = {
  stories: ['../src/**/*.stories.tsx'],
  addons: [
    '@storybook/addon-essentials',
  ],
  framework: {
    name: '@storybook/react-webpack5',
  },
  webpackFinal: async (config) => {
    // Resolve .tsx / .ts
    config.resolve.extensions = ['.tsx', '.ts', '.jsx', '.js', '.css'];
    return config;
  },
};
