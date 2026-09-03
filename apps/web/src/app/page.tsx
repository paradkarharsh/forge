'use client';

import React from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  ChevronDown,
  Code2,
  Play,
  Shield,
  Sparkles,
  Users,
} from 'lucide-react';
import { ForgeLogo } from '@/components/brand/forge-logo';
import { ThemeToggle } from '@/components/theme/theme-toggle';
import { HeroProductMockup } from '@/components/landing/hero-product-mockup';

export default function HomePage() {
  const defaultWorkspaceId = 'default';

  return (
    <div className="min-h-screen bg-[var(--forge-bg)] text-[var(--forge-text-primary)] flex flex-col font-sans selection:bg-[var(--forge-accent)] selection:text-[var(--forge-accent-foreground)] overflow-x-hidden">
      {/* ------------------------------------------------ */}
      {/* Subtle Atmospheric Wave & Radial Background Texture */}
      {/* ------------------------------------------------ */}
      <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden">
        {/* Soft warm radial illumination */}
        <div className="absolute -top-32 right-1/4 w-[700px] h-[550px] bg-radial from-[#e2caa6]/7 via-[#78b18a]/3 to-transparent blur-3xl opacity-70" />
        <div className="absolute top-1/3 left-1/4 w-[600px] h-[450px] bg-radial from-[#78b18a]/4 via-[#e2caa6]/3 to-transparent blur-3xl opacity-50" />

        {/* Faint subtle wave/topographic vector texture in background */}
        <svg
          className="absolute inset-0 w-full h-full opacity-[0.035] stroke-current text-[var(--forge-text-primary)]"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern id="heroWavePattern" width="120" height="120" patternUnits="userSpaceOnUse">
              <path d="M0 60 Q30 40 60 60 T120 60" fill="none" strokeWidth="0.75" />
              <path d="M0 120 Q30 100 60 120 T120 120" fill="none" strokeWidth="0.75" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#heroWavePattern)" />
        </svg>
      </div>

      {/* ------------------------------------------------ */}
      {/* 1. TOP NAVBAR (Restrained, thin, horizontally balanced) */}
      {/* ------------------------------------------------ */}
      <header className="sticky top-0 z-50 border-b border-[var(--forge-border)] bg-[var(--forge-bg)]/90 backdrop-blur-md px-4 sm:px-8 h-13 flex items-center justify-between transition-colors">
        {/* Left: Forge Logo */}
        <div className="flex items-center gap-8">
          <Link href="/" className="hover:opacity-90 transition-opacity">
            <ForgeLogo size="sm" showTagline={false} />
          </Link>

          {/* Center Navigation Links matching reference A */}
          <nav className="hidden lg:flex items-center gap-6 text-xs text-[var(--forge-text-secondary)] font-medium">
            <div className="flex items-center gap-1 cursor-pointer hover:text-[var(--forge-text-primary)] transition-colors">
              <span>Product</span>
              <ChevronDown className="h-3 w-3 text-[var(--forge-text-muted)]" />
            </div>
            <div className="flex items-center gap-1 cursor-pointer hover:text-[var(--forge-text-primary)] transition-colors">
              <span>Solutions</span>
              <ChevronDown className="h-3 w-3 text-[var(--forge-text-muted)]" />
            </div>
            <a href="#pricing" className="hover:text-[var(--forge-text-primary)] transition-colors">
              Pricing
            </a>
            <a href="#docs" className="hover:text-[var(--forge-text-primary)] transition-colors">
              Docs
            </a>
            <a href="#changelog" className="hover:text-[var(--forge-text-primary)] transition-colors">
              Changelog
            </a>
            <div className="flex items-center gap-1 cursor-pointer hover:text-[var(--forge-text-primary)] transition-colors">
              <span>Company</span>
              <ChevronDown className="h-3 w-3 text-[var(--forge-text-muted)]" />
            </div>
          </nav>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link
            href={`/workspaces/${defaultWorkspaceId}`}
            className="text-xs font-medium text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] px-2.5 py-1.5 transition-colors hidden sm:inline-block"
          >
            Sign in
          </Link>
          <Link
            href={`/workspaces/${defaultWorkspaceId}/agents/new`}
            className="inline-flex items-center gap-1.5 rounded-md bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-3.5 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors"
          >
            <span>Get started</span>
          </Link>
        </div>
      </header>

      {/* ------------------------------------------------ */}
      {/* 2. HERO SECTION (Dominant Two-Column Viewport) */}
      {/* ------------------------------------------------ */}
      <section className="relative pt-6 sm:pt-10 pb-8 px-4 sm:px-8 max-w-7xl mx-auto w-full">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-center">
          {/* Left Column: Typography, CTAs, Trust Indicators (~42%) */}
          <div className="lg:col-span-5 space-y-5 text-left">
            {/* Small Product Category Badge */}
            <div className="inline-flex items-center gap-2 rounded-full border border-[var(--forge-border)] bg-[var(--forge-surface)] px-3 py-1 text-[11px] font-mono text-[var(--forge-text-secondary)] uppercase tracking-wider shadow-2xs">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--forge-success)] animate-pulse" />
              <span>AI-POWERED DEVELOPMENT PLATFORM</span>
            </div>

            {/* Large Headline: warm white + soft champagne accent */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-[var(--forge-text-primary)] leading-[1.06]">
              Build better.
              <br />
              Ship faster.
              <br />
              <span className="text-[var(--forge-champagne)]">With AI agents.</span>
            </h1>

            {/* Short Supporting Paragraph */}
            <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] leading-relaxed font-normal max-w-lg">
              Forge helps engineering teams plan, build, and ship production-ready software with autonomous AI agents that work alongside your developers.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Link
                href={`/workspaces/${defaultWorkspaceId}/agents/new`}
                className="inline-flex items-center gap-2 rounded-md bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-5 py-2.5 text-xs sm:text-sm font-semibold text-[var(--forge-accent-foreground)] shadow-sm transition-colors"
              >
                <span>Start building for free</span>
                <ArrowRight className="h-4 w-4" />
              </Link>

              <a
                href="#demo"
                className="inline-flex items-center gap-2 rounded-md border border-[var(--forge-border)] bg-[var(--forge-surface)] hover:bg-[var(--forge-surface-secondary)] hover:border-[var(--forge-border-highlight)] px-4 py-2.5 text-xs sm:text-sm font-medium text-[var(--forge-text-primary)] transition-colors"
              >
                <span>Book a demo</span>
              </a>
            </div>

            {/* Trust / Value Indicators matching reference */}
            <div className="pt-3 border-t border-[var(--forge-border-subtle)] flex flex-wrap items-center gap-4 text-[11px] text-[var(--forge-text-muted)]">
              <div className="flex items-center gap-1.5">
                <Shield className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
                <span>Enterprise-grade security</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Code2 className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
                <span>Your code, your control</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
                <span>Loved by engineering teams</span>
              </div>
            </div>
          </div>

          {/* Right Column: Dominant Large Forge Product Preview (~58%) */}
          <div className="lg:col-span-7">
            <HeroProductMockup />
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ */}
      {/* 3. TRUST SECTION ("TRUSTED BY ENGINEERING TEAMS AT") */}
      {/* ------------------------------------------------ */}
      <section className="py-10 border-y border-[var(--forge-border)] bg-[var(--forge-surface)]/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-8 space-y-5 text-center">
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[var(--forge-text-muted)] font-medium">
            TRUSTED BY ENGINEERING TEAMS AT
          </p>

          <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-14 text-sm font-bold text-[var(--forge-text-muted)] tracking-wide opacity-85">
            <div className="flex items-center gap-2 hover:text-[var(--forge-text-primary)] transition-colors">
              <span className="text-base font-black">▲</span>
              <span>Acme Inc.</span>
            </div>
            <div className="flex items-center gap-2 hover:text-[var(--forge-text-primary)] transition-colors">
              <span className="text-base font-black">✻</span>
              <span>Nebula</span>
            </div>
            <div className="flex items-center gap-2 hover:text-[var(--forge-text-primary)] transition-colors">
              <span className="text-base font-black">⬢</span>
              <span>StackOne</span>
            </div>
            <div className="flex items-center gap-2 hover:text-[var(--forge-text-primary)] transition-colors">
              <span className="text-base font-black">☁</span>
              <span>Cloudscape</span>
            </div>
            <div className="flex items-center gap-2 hover:text-[var(--forge-text-primary)] transition-colors">
              <span className="text-base font-bold font-mono">s</span>
              <span>statamic</span>
            </div>
            <div className="flex items-center gap-2 hover:text-[var(--forge-text-primary)] transition-colors">
              <span className="text-base font-black">∞</span>
              <span>Aceternity</span>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ */}
      {/* 4. FEATURE SECTION ("Everything you need to build with AI") */}
      {/* ------------------------------------------------ */}
      <section className="py-16 sm:py-20 px-4 sm:px-8 max-w-6xl mx-auto w-full space-y-12">
        <div className="text-center space-y-3 max-w-xl mx-auto">
          <div className="inline-flex items-center gap-1.5 text-[11px] font-mono text-[var(--forge-champagne)] uppercase tracking-wider">
            <span>◆</span>
            <span>BUILT FOR MODERN DEVELOPMENT</span>
          </div>

          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[var(--forge-text-primary)] leading-tight">
            Everything you need to
            <br />
            build with AI
          </h2>
        </div>

        {/* 4 Cards Horizontal Grid matching Reference A */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Feature 1 */}
          <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 flex flex-col justify-between space-y-4 hover:border-[var(--forge-border-highlight)] transition-colors group">
            <div className="space-y-3">
              <div className="h-8 w-8 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-accent)]">
                <Sparkles className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-[var(--forge-text-primary)]">
                AI agents that deliver
              </h3>
              <p className="text-xs text-[var(--forge-text-secondary)] leading-relaxed">
                Autonomous agents that understand your codebase, plan complex tasks, and ship production-ready changes.
              </p>
            </div>
            <div className="flex items-center text-xs font-mono text-[var(--forge-text-muted)] group-hover:text-[var(--forge-text-primary)] group-hover:translate-x-1 transition-all pt-2">
              <ArrowRight className="h-3.5 w-3.5" />
            </div>
          </div>

          {/* Feature 2 */}
          <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 flex flex-col justify-between space-y-4 hover:border-[var(--forge-border-highlight)] transition-colors group">
            <div className="space-y-3">
              <div className="h-8 w-8 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-accent)]">
                <Code2 className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-[var(--forge-text-primary)]">
                Deep codebase context
              </h3>
              <p className="text-xs text-[var(--forge-text-secondary)] leading-relaxed">
                Index, search, and understand your entire codebase in seconds. Built on RAG and graph-powered understanding.
              </p>
            </div>
            <div className="flex items-center text-xs font-mono text-[var(--forge-text-muted)] group-hover:text-[var(--forge-text-primary)] group-hover:translate-x-1 transition-all pt-2">
              <ArrowRight className="h-3.5 w-3.5" />
            </div>
          </div>

          {/* Feature 3 */}
          <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 flex flex-col justify-between space-y-4 hover:border-[var(--forge-border-highlight)] transition-colors group">
            <div className="space-y-3">
              <div className="h-8 w-8 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-accent)]">
                <Shield className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-[var(--forge-text-primary)]">
                Safe by design
              </h3>
              <p className="text-xs text-[var(--forge-text-secondary)] leading-relaxed">
                Human-in-the-loop approvals, permission controls, and audit trails keep you in control at every step.
              </p>
            </div>
            <div className="flex items-center text-xs font-mono text-[var(--forge-text-muted)] group-hover:text-[var(--forge-text-primary)] group-hover:translate-x-1 transition-all pt-2">
              <ArrowRight className="h-3.5 w-3.5" />
            </div>
          </div>

          {/* Feature 4 */}
          <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 flex flex-col justify-between space-y-4 hover:border-[var(--forge-border-highlight)] transition-colors group">
            <div className="space-y-3">
              <div className="h-8 w-8 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-accent)]">
                <Users className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold text-[var(--forge-text-primary)]">
                Built for teams
              </h3>
              <p className="text-xs text-[var(--forge-text-secondary)] leading-relaxed">
                Collaborate with your team, share agents, and maintain velocity across your entire organization.
              </p>
            </div>
            <div className="flex items-center text-xs font-mono text-[var(--forge-text-muted)] group-hover:text-[var(--forge-text-primary)] group-hover:translate-x-1 transition-all pt-2">
              <ArrowRight className="h-3.5 w-3.5" />
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ */}
      {/* 5. PRODUCT DEMO SECTION ("See Forge in action") */}
      {/* ------------------------------------------------ */}
      <section id="demo" className="py-10 px-4 sm:px-8 max-w-6xl mx-auto w-full">
        <div className="rounded-2xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-6 sm:p-10 flex flex-col lg:flex-row items-center justify-between gap-8 shadow-xl relative overflow-hidden">
          {/* Background subtle illumination */}
          <div className="absolute top-0 right-1/3 w-96 h-96 bg-radial from-[#78B18A]/8 via-[#e2caa6]/4 to-transparent blur-3xl pointer-events-none" />

          {/* Left Text & CTA */}
          <div className="space-y-4 max-w-md text-left z-10">
            <h3 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--forge-text-primary)]">
              See Forge in action
            </h3>
            <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] leading-relaxed">
              Book a personalized demo and see how Forge can transform your development workflow.
            </p>
            <div className="pt-2">
              <Link
                href={`/workspaces/${defaultWorkspaceId}/agents/new`}
                className="inline-flex items-center gap-2 rounded-md bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-4 py-2 text-xs font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors"
              >
                <span>Book a demo</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>

          {/* Right Video / Preview Card */}
          <div className="w-full lg:w-96 rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-6 flex items-center gap-4 z-10 shadow-lg cursor-pointer hover:border-[var(--forge-border-highlight)] transition-colors group">
            {/* Play Button */}
            <div className="h-12 w-12 rounded-full bg-[var(--forge-accent)] text-[var(--forge-accent-foreground)] flex items-center justify-center shadow-md group-hover:scale-105 transition-transform shrink-0">
              <Play className="h-5 w-5 fill-current ml-0.5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-[var(--forge-text-primary)]">
                Watch demo
              </p>
              <p className="text-[11px] font-mono text-[var(--forge-text-muted)]">
                2 min overview
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ */}
      {/* 6. FINAL CTA ("Build the future of software.") */}
      {/* ------------------------------------------------ */}
      <section className="py-16 sm:py-20 px-4 sm:px-8 max-w-4xl mx-auto w-full text-center space-y-5">
        <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--forge-text-primary)] leading-tight">
          Build the future of software.
        </h2>
        <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] max-w-lg mx-auto leading-relaxed">
          Start building production-ready software with autonomous AI agents that understand your codebase and respect your controls.
        </p>
        <div className="pt-2">
          <Link
            href={`/workspaces/${defaultWorkspaceId}/agents/new`}
            className="inline-flex items-center gap-2 rounded-md bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-6 py-3 text-xs sm:text-sm font-semibold text-[var(--forge-accent-foreground)] shadow-sm transition-colors"
          >
            <span>Start building for free</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* ------------------------------------------------ */}
      {/* 7. CLEAN FOOTER */}
      {/* ------------------------------------------------ */}
      <footer className="border-t border-[var(--forge-border)] bg-[var(--forge-surface)] py-8 px-4 sm:px-8 mt-auto text-xs text-[var(--forge-text-muted)]">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <ForgeLogo size="sm" showTagline={false} />
            <span className="font-mono text-[10px] tracking-wider uppercase text-[var(--forge-text-muted)]">
              BUILD BETTER. SHIP FASTER.
            </span>
          </div>

          <div className="flex items-center gap-5 text-xs font-mono">
            <a href="https://github.com/paradkarharsh/forge" target="_blank" rel="noopener noreferrer" className="hover:text-[var(--forge-text-primary)] transition-colors">
              GitHub
            </a>
            <Link href={`/workspaces/${defaultWorkspaceId}`} className="hover:text-[var(--forge-text-primary)] transition-colors">
              Workspace
            </Link>
            <span>
              © {new Date().getFullYear()} Forge.
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
