'use client'

import { useRef, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { login, register } from '../../services/auth'

// 密码强度：0-4 分
function calcStrength(pwd: string): number {
  if (!pwd) return 0
  let score = 0
  if (pwd.length >= 8) score++
  if (/[A-Z]/.test(pwd)) score++
  if (/[0-9]/.test(pwd)) score++
  if (/[^A-Za-z0-9]/.test(pwd)) score++
  return score
}

const STRENGTH_LABELS = ['', '弱', '一般', '较强', '强']
const STRENGTH_TEXT_COLORS = ['', 'text-red-500', 'text-yellow-600', 'text-blue-500', 'text-green-500']

function strengthBarColor(barIndex: number, score: number): string {
  if (score <= barIndex) return 'bg-gray-200'
  if (score === 1) return 'bg-red-400'
  if (score === 2) return barIndex === 0 ? 'bg-red-400' : 'bg-yellow-400'
  if (score === 3) return barIndex < 2 ? 'bg-blue-400' : 'bg-blue-400'
  return 'bg-green-400'
}

export default function AuthPage() {
  const router = useRouter()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [showRegPwd, setShowRegPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const asideRef = useRef<HTMLElement>(null)
  const charsRef = useRef<HTMLDivElement>(null)

  const strength = calcStrength(password)

  // 角色动画：鼠标追踪 + 随机眨眼（直接操作 DOM，避免频繁 re-render）
  useEffect(() => {
    const aside = asideRef.current
    const chars = charsRef.current
    if (!aside || !chars) return

    let lx = 0, ly = 0
    let purpleBlink = false, darkBlink = false
    const timers: ReturnType<typeof setTimeout>[] = []

    function clamp(v: number, mn: number, mx: number) {
      return Math.max(mn, Math.min(mx, v))
    }

    function render() {
      const charPurple   = chars!.querySelector<HTMLElement>('.char-purple')
      const purpleEyes   = chars!.querySelector<HTMLElement>('.char-purple-eyes')
      const eyePL        = chars!.querySelector<HTMLElement>('.eye-p-l')
      const eyePR        = chars!.querySelector<HTMLElement>('.eye-p-r')
      const charDark     = chars!.querySelector<HTMLElement>('.char-dark')
      const darkEyes     = chars!.querySelector<HTMLElement>('.char-dark-eyes')
      const eyeDL        = chars!.querySelector<HTMLElement>('.eye-d-l')
      const eyeDR        = chars!.querySelector<HTMLElement>('.eye-d-r')
      const charOrange   = chars!.querySelector<HTMLElement>('.char-orange')
      const orangePupils = chars!.querySelector<HTMLElement>('.char-orange-pupils')
      const charYellow   = chars!.querySelector<HTMLElement>('.char-yellow')
      const yellowPupils = chars!.querySelector<HTMLElement>('.char-yellow-pupils')
      const yellowMouth  = chars!.querySelector<HTMLElement>('.char-yellow-mouth')

      if (charPurple)   charPurple.style.transform = `skewX(${clamp(-lx*6,-6,6)}deg)`
      if (purpleEyes) { purpleEyes.style.left = `${45+lx*15}px`; purpleEyes.style.top = `${40+ly*10}px` }
      if (eyePL) eyePL.style.height = purpleBlink ? '2px' : '18px'
      if (eyePR) eyePR.style.height = purpleBlink ? '2px' : '18px'
      purpleEyes?.querySelectorAll<HTMLElement>('.pupil')
        .forEach(p => { p.style.transform = `translate(${lx*5}px,${ly*5}px)` })

      if (charDark)   charDark.style.transform = `skewX(${clamp(-lx*4.5,-6,6)}deg)`
      if (darkEyes) { darkEyes.style.left = `${26+lx*12}px`; darkEyes.style.top = `${32+ly*10}px` }
      if (eyeDL) eyeDL.style.height = darkBlink ? '2px' : '16px'
      if (eyeDR) eyeDR.style.height = darkBlink ? '2px' : '16px'
      darkEyes?.querySelectorAll<HTMLElement>('.pupil')
        .forEach(p => { p.style.transform = `translate(${lx*4}px,${ly*4}px)` })

      if (charOrange)   charOrange.style.transform = `skewX(${clamp(-lx*4,-6,6)}deg)`
      if (orangePupils) { orangePupils.style.left = `${82+lx*14}px`; orangePupils.style.top = `${90+ly*10}px` }
      orangePupils?.querySelectorAll<HTMLElement>('.pupil')
        .forEach(p => { p.style.transform = `translate(${lx*5}px,${ly*5}px)` })

      if (charYellow)   charYellow.style.transform = `skewX(${clamp(-lx*4,-6,6)}deg)`
      if (yellowPupils) { yellowPupils.style.left = `${52+lx*12}px`; yellowPupils.style.top = `${40+ly*10}px` }
      yellowPupils?.querySelectorAll<HTMLElement>('.pupil')
        .forEach(p => { p.style.transform = `translate(${lx*4}px,${ly*4}px)` })
      if (yellowMouth) { yellowMouth.style.left = `${40+lx*12}px`; yellowMouth.style.top = `${88+ly*10}px` }
    }

    function scheduleBlink(setVal: (v: boolean) => void) {
      const t1 = setTimeout(() => {
        setVal(true); render()
        const t2 = setTimeout(() => {
          setVal(false); render()
          scheduleBlink(setVal)
        }, 140)
        timers.push(t2)
      }, Math.random() * 4000 + 3000)
      timers.push(t1)
    }

    scheduleBlink(v => { purpleBlink = v })
    scheduleBlink(v => { darkBlink = v })

    function onMouseMove(e: MouseEvent) {
      const rect = aside!.getBoundingClientRect()
      lx = clamp(((e.clientX - rect.left) / rect.width  - 0.5) * 2, -1, 1)
      ly = clamp(((e.clientY - rect.top)  / rect.height - 0.45) * 2, -1, 1)
      render()
    }
    function onMouseLeave() { lx = 0; ly = 0; render() }

    aside.addEventListener('mousemove', onMouseMove)
    aside.addEventListener('mouseleave', onMouseLeave)
    render()

    return () => {
      aside.removeEventListener('mousemove', onMouseMove)
      aside.removeEventListener('mouseleave', onMouseLeave)
      timers.forEach(clearTimeout)
    }
  }, [])

  function switchTab(t: 'login' | 'register') {
    setTab(t); setError('')
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await login(email, password)
      router.replace('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await register(email, username, password)
      await login(email, password)
      router.replace('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid select-none lg:h-screen lg:grid-cols-[1fr_1fr] lg:overflow-hidden xl:grid-cols-[0.96fr_1.04fr]">

      {/* ═══ 左侧：渐变 + 角色 ═══ */}
      <aside
        ref={asideRef}
        className="relative hidden overflow-hidden lg:flex lg:flex-col lg:justify-between lg:px-10 lg:py-8 lg:text-white xl:px-12 xl:py-10"
        style={{ background: 'radial-gradient(circle at top left,rgba(255,255,255,0.22),transparent 28%),linear-gradient(145deg,#1e3a8a 0%,#2563eb 55%,#0f172a 100%)' }}
      >
        {/* 网格纹理 */}
        <div className="absolute inset-0 opacity-30" style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.06) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.06) 1px,transparent 1px)',
          backgroundSize: '22px 22px'
        }} />
        {/* 光晕 */}
        <div className="absolute right-20 top-24 size-56 rounded-full bg-blue-400/10 blur-3xl" />
        <div className="absolute bottom-16 left-12 size-72 rounded-full bg-blue-600/10 blur-3xl" />

        {/* 品牌 */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-2xl text-sm font-semibold"
            style={{ background: 'rgba(255,255,255,0.12)' }}>JI</div>
          <div>
            <p className="text-sm font-medium">Job Intel Agent</p>
            <p className="text-xs text-slate-200">AI 驱动的面试情报助手</p>
          </div>
        </div>

        {/* 标题 */}
        <div className="relative z-10 max-w-lg space-y-4">
          <span className="inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs uppercase tracking-[0.24em] text-white/80">
            Job Intel
          </span>
          <div className="space-y-2.5">
            <h2 className="text-[1.85rem] font-semibold leading-tight tracking-tight xl:text-[2.1rem]">
              你的面试情报助手
            </h2>
            <p className="max-w-md text-sm leading-7 text-slate-200">
              粘贴 JD 链接，上传简历<br />3 分钟生成专属面试情报报告
            </p>
          </div>
        </div>

        {/* 角色区 */}
        <div className="relative z-10 flex min-h-[180px] items-end justify-center xl:min-h-[220px]">
          <div ref={charsRef} className="relative origin-bottom scale-[0.8] xl:scale-[0.92]"
            style={{ height: 320, width: 440 }}>

            {/* 橙色大半圆 */}
            <div className="char-orange" style={{ position:'absolute',bottom:0,left:0,height:200,width:240,background:'#FF9B6B',borderRadius:'120px 120px 0 0',transformOrigin:'bottom center',transition:'transform 0.5s ease-out',zIndex:9999 }}>
              <div className="char-orange-pupils" style={{ position:'absolute',display:'flex',gap:32,left:82,top:90,transition:'left 0.15s,top 0.15s' }}>
                <div className="pupil" style={{ width:12,height:12,borderRadius:'50%',background:'#3d1f0a',transition:'transform 0.1s ease-out' }} />
                <div className="pupil" style={{ width:12,height:12,borderRadius:'50%',background:'#3d1f0a',transition:'transform 0.1s ease-out' }} />
              </div>
            </div>

            {/* 紫色高矩形 */}
            <div className="char-purple" style={{ position:'absolute',bottom:0,left:70,height:400,width:180,background:'#6C3FF5',borderRadius:'10px 10px 0 0',transformOrigin:'bottom center',transition:'transform 0.5s ease-out' }}>
              <div className="char-purple-eyes" style={{ position:'absolute',display:'flex',gap:32,left:45,top:40,transition:'left 0.15s,top 0.15s' }}>
                <div className="eye-p-l" style={{ width:18,height:18,borderRadius:'50%',background:'white',display:'flex',alignItems:'center',justifyContent:'center',overflow:'hidden',flexShrink:0,transition:'height 0.15s ease' }}>
                  <div className="pupil" style={{ width:7,height:7,borderRadius:'50%',background:'#1e293b',transition:'transform 0.1s ease-out' }} />
                </div>
                <div className="eye-p-r" style={{ width:18,height:18,borderRadius:'50%',background:'white',display:'flex',alignItems:'center',justifyContent:'center',overflow:'hidden',flexShrink:0,transition:'height 0.15s ease' }}>
                  <div className="pupil" style={{ width:7,height:7,borderRadius:'50%',background:'#1e293b',transition:'transform 0.1s ease-out' }} />
                </div>
              </div>
            </div>

            {/* 深色窄矩形 */}
            <div className="char-dark" style={{ position:'absolute',bottom:0,left:240,height:310,width:120,background:'#2D2D2D',borderRadius:'8px 8px 0 0',transformOrigin:'bottom center',transition:'transform 0.5s ease-out' }}>
              <div className="char-dark-eyes" style={{ position:'absolute',display:'flex',gap:24,left:26,top:32,transition:'left 0.15s,top 0.15s' }}>
                <div className="eye-d-l" style={{ width:16,height:16,borderRadius:'50%',background:'white',display:'flex',alignItems:'center',justifyContent:'center',overflow:'hidden',flexShrink:0,transition:'height 0.15s ease' }}>
                  <div className="pupil" style={{ width:6,height:6,borderRadius:'50%',background:'#2D2D2D',transition:'transform 0.1s ease-out' }} />
                </div>
                <div className="eye-d-r" style={{ width:16,height:16,borderRadius:'50%',background:'white',display:'flex',alignItems:'center',justifyContent:'center',overflow:'hidden',flexShrink:0,transition:'height 0.15s ease' }}>
                  <div className="pupil" style={{ width:6,height:6,borderRadius:'50%',background:'#2D2D2D',transition:'transform 0.1s ease-out' }} />
                </div>
              </div>
            </div>

            {/* 黄色拱形 */}
            <div className="char-yellow" style={{ position:'absolute',bottom:0,left:310,height:230,width:140,background:'#E8D754',borderRadius:'70px 70px 0 0',transformOrigin:'bottom center',transition:'transform 0.5s ease-out' }}>
              <div className="char-yellow-pupils" style={{ position:'absolute',display:'flex',gap:24,left:52,top:40,transition:'left 0.15s,top 0.15s' }}>
                <div className="pupil" style={{ width:12,height:12,borderRadius:'50%',background:'#3d3400',transition:'transform 0.1s ease-out' }} />
                <div className="pupil" style={{ width:12,height:12,borderRadius:'50%',background:'#3d3400',transition:'transform 0.1s ease-out' }} />
              </div>
              <div className="char-yellow-mouth" style={{ position:'absolute',height:4,width:80,borderRadius:99,background:'#2D2D2D',left:40,top:88,transition:'left 0.15s,top 0.15s' }} />
            </div>

          </div>
        </div>

        {/* 底部关键词 */}
        <div className="relative z-10 flex flex-wrap gap-6 text-sm text-slate-200/90">
          <span>深度调研</span><span>题目预测</span><span>薪资情报</span>
        </div>
      </aside>

      {/* ═══ 右侧：登录/注册表单 ═══ */}
      <section className="flex flex-1 items-center justify-center px-6 py-12 bg-gray-50">
        <div className="w-full max-w-md">

          {/* Logo */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-600 mb-4 shadow-md">
              <span className="text-white text-xl">🧠</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">
              {tab === 'login' ? '欢迎回来' : '创建账号'}
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              {tab === 'login'
                ? '登录以继续使用 Job Intel Agent'
                : '注册后即可开始生成面试情报报告'}
            </p>
          </div>

          {/* Tab 切换 */}
          <div className="bg-gray-200 rounded-xl p-1 flex mb-6">
            <button onClick={() => switchTab('login')}
              className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${tab === 'login' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'}`}>
              登录
            </button>
            <button onClick={() => switchTab('register')}
              className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${tab === 'register' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'}`}>
              注册
            </button>
          </div>

          {/* 表单卡片 */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6" style={{ minHeight: 340 }}>
            {error && (
              <p className="text-sm text-red-500 mb-4 text-center bg-red-50 rounded-lg py-2 px-3">
                {error}
              </p>
            )}

            {tab === 'login' ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">邮箱</label>
                  <div className="relative">
                    <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                      placeholder="you@example.com" required autoComplete="email"
                      className="w-full rounded-xl border border-gray-300 bg-white pl-10 pr-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-sm font-medium text-gray-700">密码</label>
                    <a href="#" className="text-xs text-blue-600 hover:underline">忘记密码？</a>
                  </div>
                  <div className="relative">
                    <input type={showPwd ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                      placeholder="请输入密码" required autoComplete="current-password"
                      className="w-full rounded-xl border border-gray-300 bg-white pl-4 pr-11 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                    <button type="button" onClick={() => setShowPwd(v => !v)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        {showPwd
                          ? <><path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></>
                          : <><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></>
                        }
                      </svg>
                    </button>
                  </div>
                </div>
                <button type="submit" disabled={loading}
                  className="w-full rounded-xl bg-blue-600 py-3 text-white font-semibold text-sm hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-60">
                  {loading ? '登录中…' : '登录'}
                </button>
                <p className="text-center text-sm text-gray-500 pt-1">
                  没有账号？
                  <button type="button" onClick={() => switchTab('register')}
                    className="text-blue-600 font-medium hover:underline ml-1">免费注册</button>
                </p>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">邮箱</label>
                  <div className="relative">
                    <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                      placeholder="you@example.com" required autoComplete="email"
                      className="w-full rounded-xl border border-gray-300 bg-white pl-10 pr-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">用户名</label>
                  <input type="text" value={username} onChange={e => setUsername(e.target.value)}
                    placeholder="你的昵称" required autoComplete="username"
                    className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
                  <div className="relative">
                    <input type={showRegPwd ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                      placeholder="至少 8 位，包含字母和数字" required autoComplete="new-password"
                      className="w-full rounded-xl border border-gray-300 bg-white pl-4 pr-11 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                    <button type="button" onClick={() => setShowRegPwd(v => !v)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        {showRegPwd
                          ? <><path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></>
                          : <><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></>
                        }
                      </svg>
                    </button>
                  </div>
                  {password && (
                    <>
                      <div className="flex gap-1 mt-2">
                        {[0,1,2,3].map(i => (
                          <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${strengthBarColor(i, strength)}`} />
                        ))}
                      </div>
                      <p className={`text-xs mt-1 ${STRENGTH_TEXT_COLORS[strength]}`}>
                        密码强度：{STRENGTH_LABELS[strength]}
                      </p>
                    </>
                  )}
                </div>
                <button type="submit" disabled={loading}
                  className="w-full rounded-xl bg-blue-600 py-3 text-white font-semibold text-sm hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-60">
                  {loading ? '注册中…' : '创建账号'}
                </button>
                <p className="text-center text-sm text-gray-500 pt-1">
                  已有账号？
                  <button type="button" onClick={() => switchTab('login')}
                    className="text-blue-600 font-medium hover:underline ml-1">立即登录</button>
                </p>
              </form>
            )}
          </div>

        </div>
      </section>
    </div>
  )
}
