import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Metric, money } from '../main'

test('money formats numbers and empty', ()=>{
  expect(money(null)).toBe('—')
  expect(money(1234.5)).toBe('1,234.5') // locale may vary; fallback asserts contains
})

test('Metric displays label and value', ()=>{
  render(<Metric label="股價" value={"100"} />)
  expect(screen.getByText('股價')).toBeInTheDocument()
  expect(screen.getByText('100')).toBeInTheDocument()
})
