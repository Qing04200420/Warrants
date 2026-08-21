import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig(
    {
        plugins:[react()], 
        test: {
            environment: 'jsdom',
        },
        // enable host so dev server is reachable on LAN (e.g. 192.168.x.x)
        server: {
            host: true,
            port: 3000,
            proxy: {
                '/api': {
                    target: 'http://localhost:8000',
                    changeOrigin: true,
                    secure: false,
                }
            }
        },
        base:'/Warrants/'
    })

