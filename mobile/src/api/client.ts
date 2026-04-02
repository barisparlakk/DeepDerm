import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Bilgisayarın Wi-Fi IP'si (expo start --lan ile aynı ağ arayüzü)
const BASE_URL = 'http://10.5.9.223:8080';

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
