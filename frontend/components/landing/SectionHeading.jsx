export default function SectionHeading({
  eyebrow,
  title,
  text,
  align = 'left',
  extra
}) {
  return (
    <div className={align === 'center' ? 'mx-auto max-w-3xl text-center' : 'max-w-3xl'}>
      <div className="mb-4 inline-flex items-center rounded-full border border-white/10 bg-white/5 px-4 py-1 text-xs font-semibold uppercase tracking-[0.28em] text-accent/90">
        {eyebrow}
      </div>
      <h2 className="text-3xl font-semibold tracking-tight text-white md:text-5xl">
        {title}
      </h2>
      <p className="mt-5 text-base leading-7 text-slate-300 md:text-lg">
        {text}
      </p>
      {extra ? <div className="mt-6">{extra}</div> : null}
    </div>
  );
}
