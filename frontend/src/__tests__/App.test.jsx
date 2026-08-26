import React from 'react'
import { render, screen, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { test, expect } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { App, Metric, StockScorePage, businessDaysBetween, calculateBlackScholesWarrant, getPageFromHash, money } from '../main'
import { store } from '../store'

test('money formats numbers and empty', ()=>{
  expect(money(null)).toBe('—')
  expect(money(1234.5)).toBe('1,234.5') // locale may vary; fallback asserts contains
})

test('Metric displays label and value', ()=>{
  render(<Metric label="股價" value={"100"} />)
  expect(screen.getByText('股價')).toBeInTheDocument()
  expect(screen.getByText('100')).toBeInTheDocument()
})

test('calculateBlackScholesWarrant estimates the example directly', ()=>{
  const result=calculateBlackScholesWarrant(130,120,0.1,90)
  expect(result.intrinsicValue).toBe(1)
  expect(result.timeValue).toBeCloseTo(0.3768,3)
  expect(result.warrantPrice).toBeCloseTo(1.3768,3)
})

test('calculateBlackScholesWarrant equals intrinsic value at expiry', ()=>{
  expect(calculateBlackScholesWarrant(130,120,0.1,0)).toEqual({
    intrinsicValue:1,
    timeValue:0,
    warrantPrice:1,
    d1:null,
    d2:null,
  })
})

test('calculateBlackScholesWarrant waits for complete valid input', ()=>{
  expect(calculateBlackScholesWarrant('',120,0.1,90)).toBeNull()
  expect(calculateBlackScholesWarrant(130,120,-0.1,90)).toBeNull()
})

test('calculateBlackScholesWarrant supports put warrants', ()=>{
  const result=calculateBlackScholesWarrant(80,100,0.05,30,{volatility:0.25,riskFreeRate:0.015,daysPerYear:252,callPut:'P'})
  expect(result.intrinsicValue).toBe(1)
  expect(result.warrantPrice).toBeGreaterThanOrEqual(1)
})

test('businessDaysBetween excludes weekends', ()=>{
  expect(businessDaysBetween('2026-08-21','2026-08-24')).toBe(1)
  expect(businessDaysBetween('2026-08-21','2026-08-24',['2026-08-24'])).toBe(0)
})

test('StockScorePage requires a complete trade plan', ()=>{
  render(<Provider store={store}><StockScorePage /></Provider>)
  expect(screen.getByRole('heading',{name:'股票標的評分'})).toBeInTheDocument()
  expect(screen.getByRole('button',{name:'開始評分'})).toBeDisabled()
  expect(screen.getByLabelText('股票代號')).toHaveValue('2330')
})

test('empty hash defaults to stock score page', ()=>{
  expect(getPageFromHash('')).toBe('stock-score')
  window.location.hash=''
  const view=render(<Provider store={store}><App /></Provider>)
  expect(within(view.container).getByRole('heading',{name:'股票標的評分'})).toBeInTheDocument()
})

test('unknown hash renders 404 page', ()=>{
  expect(getPageFromHash('#missing-page')).toBe('not-found')
  window.location.hash='#missing-page'
  const view=render(<Provider store={store}><App /></Provider>)
  expect(within(view.container).getByRole('heading',{name:'找不到此頁面'})).toBeInTheDocument()
  expect(within(view.container).getByRole('link',{name:'返回標的評分'})).toHaveAttribute('href','#stock-score')
})
