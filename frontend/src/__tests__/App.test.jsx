import React from 'react'
import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { Metric, calculateWarrantValues, money } from '../main'

test('money formats numbers and empty', ()=>{
  expect(money(null)).toBe('—')
  expect(money(1234.5)).toBe('1,234.5') // locale may vary; fallback asserts contains
})

test('Metric displays label and value', ()=>{
  render(<Metric label="股價" value={"100"} />)
  expect(screen.getByText('股價')).toBeInTheDocument()
  expect(screen.getByText('100')).toBeInTheDocument()
})

test('calculateWarrantValues matches the example', ()=>{
  expect(calculateWarrantValues(130,120,0.1,1.5)).toEqual({
    intrinsicValue:1,
    timeValue:0.5,
    warrantPrice:1.5,
  })
})

test('calculateWarrantValues keeps intrinsic value at zero when out of the money', ()=>{
  expect(calculateWarrantValues(110,120,0.1,0.4)).toEqual({
    intrinsicValue:0,
    timeValue:0.4,
    warrantPrice:0.4,
  })
})

test('calculateWarrantValues waits for complete valid input', ()=>{
  expect(calculateWarrantValues('',120,0.1,1.5)).toBeNull()
  expect(calculateWarrantValues(130,120,-0.1,1.5)).toBeNull()
})
