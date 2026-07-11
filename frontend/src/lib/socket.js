import { io } from 'socket.io-client';
import { BACKEND_URL } from './api.js';

// Socket.IO mounted at root path on backend
const socket = io(BACKEND_URL, {
  transports: ['websocket', 'polling'],
  autoConnect: true,
  withCredentials: true,
  reconnection: true,
});

socket.on('connect', () => console.log('[socket] connected', socket.id));
socket.on('disconnect', () => console.log('[socket] disconnected'));
socket.on('connect_error', (err) => console.warn('[socket] error', err.message));

export default socket;
