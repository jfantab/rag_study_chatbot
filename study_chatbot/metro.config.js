const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Add resolver configuration for remaining polyfills
config.resolver.extraNodeModules = {
  buffer: require.resolve('buffer/'),
};

// Enable package exports for proper module resolution
config.resolver.unstable_enablePackageExports = true;

module.exports = config;
