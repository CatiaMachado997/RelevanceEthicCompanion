module.exports = {
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['./jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  transform: {
    '^.+\.(ts|tsx)$': ['ts-jest', {
      babelConfig: {
        presets: [
          ['@babel/preset-react', {
            runtime: 'automatic'
          }]
        ]
      }
    }],
  },
};