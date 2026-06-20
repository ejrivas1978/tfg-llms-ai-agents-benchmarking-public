/**
 * Modulo: services/uploadApi
 * Ruta:   frontend/src/services/uploadApi.ts
 *
 * Descripcion:
 *   Capa de acceso al endpoint de extraccion de texto desde ficheros.
 *   Envia el fichero como multipart/form-data y devuelve el texto extraido,
 *   el numero de palabras y si fue truncado al limite de 5000 palabras.
 *
 * Sprint: Sprint 4
 */

import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

export interface TextoExtraido {
  texto:    string
  palabras: number
  truncado: boolean
}

export async function extraerTextoFichero(archivo: File): Promise<TextoExtraido> {
  const formulario = new FormData()
  formulario.append('archivo', archivo)
  const { data } = await api.post<TextoExtraido>('/upload/extraer-texto', formulario, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
