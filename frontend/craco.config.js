import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default {
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
};
