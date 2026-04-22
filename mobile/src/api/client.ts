import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// İnternet üzerinden erişim için ngrok tunnel adresi (Spring Boot)
const BASE_URL = 'https://self-hazy-glandular.ngrok-free.dev';

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
