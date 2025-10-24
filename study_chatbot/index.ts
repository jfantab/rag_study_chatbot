// Polyfills for crypto functionality required by AWS Cognito
import * as Crypto from 'expo-crypto';
import 'react-native-url-polyfill/auto';
import { Buffer } from 'buffer';

// Setup Buffer global
global.Buffer = Buffer;

// Setup crypto global using expo-crypto
global.crypto = {
  getRandomValues: (array: Uint8Array) => {
    // expo-crypto's getRandomBytes returns a Uint8Array
    const randomBytes = Crypto.getRandomBytes(array.length);
    array.set(randomBytes);
    return array;
  },
  // Provide a basic subtle crypto implementation for Cognito
  subtle: {
    digest: async (algorithm: string | { name: string }, data: BufferSource) => {
      const algorithmName = typeof algorithm === 'string' ? algorithm : algorithm.name;
      let cryptoAlgorithm: Crypto.CryptoDigestAlgorithm;

      // Map Web Crypto API algorithm names to expo-crypto algorithms
      if (algorithmName.includes('SHA-256') || algorithmName.includes('SHA256')) {
        cryptoAlgorithm = Crypto.CryptoDigestAlgorithm.SHA256;
      } else if (algorithmName.includes('SHA-384') || algorithmName.includes('SHA384')) {
        cryptoAlgorithm = Crypto.CryptoDigestAlgorithm.SHA384;
      } else if (algorithmName.includes('SHA-512') || algorithmName.includes('SHA512')) {
        cryptoAlgorithm = Crypto.CryptoDigestAlgorithm.SHA512;
      } else if (algorithmName.includes('SHA-1') || algorithmName.includes('SHA1')) {
        cryptoAlgorithm = Crypto.CryptoDigestAlgorithm.SHA1;
      } else {
        throw new Error(`Unsupported algorithm: ${algorithmName}`);
      }

      // Convert data to string for expo-crypto
      const dataArray = new Uint8Array(data as ArrayBuffer);
      const dataString = Array.from(dataArray)
        .map(b => String.fromCharCode(b))
        .join('');

      const hash = await Crypto.digestStringAsync(
        cryptoAlgorithm,
        dataString,
        { encoding: Crypto.CryptoEncoding.HEX }
      );

      // Convert hex string back to ArrayBuffer
      const hashArray = new Uint8Array(hash.match(/.{1,2}/g)!.map(byte => parseInt(byte, 16)));
      return hashArray.buffer;
    },
  },
} as any;

import { registerRootComponent } from 'expo';

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
