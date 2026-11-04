import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({base:'./',plugins:[vue({template:{transformAssetUrls:false}})],define:{'import.meta.env.VITE_LST_BROWSER':JSON.stringify(process.env.LST_SERVER==='1'?'0':'1')},server:{host:'127.0.0.1',port:5197,strictPort:true,proxy:{'/api':'http://127.0.0.1:8771'}},build:{outDir:'dist',chunkSizeWarningLimit:950}})
