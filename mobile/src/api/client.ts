import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const envApiUrl = process.env.EXPO_PUBLIC_API_URL?.trim();

const expoHostUri = Constants.expoConfig?.hostUri ?? '';
const expoHost = expoHostUri.split(':')[0] ?? '';
const isExpoTunnelHost = expoHost.endsWith('.exp.direct') || expoHost.endsWith('.expo.dev');

const debuggerHostRaw =
  (Constants as any)?.expoGoConfig?.debuggerHost ??
  (Constants as any)?.manifest2?.extra?.expoClient?.debuggerHost ??
  '';
const debuggerHost = typeof debuggerHostRaw === 'string'
  ? debuggerHostRaw.split(':')[0]
  : '';

const autoHost = debuggerHost || expoHost;

const BASE_URL = envApiUrl
  ? envApiUrl
  : autoHost && !isExpoTunnelHost
    ? `http://${autoHost}:8080`
    : autoHost && debuggerHost
      ? `http://${autoHost}:8080`
      : 'http://localhost:8080';

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT to every request
client.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('deepderm_patient_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default client;
