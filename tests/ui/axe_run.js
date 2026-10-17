async () => {
  const r = await axe.run(document, {runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa', 'best-practice']});
  return r.violations.map(v => ({id: v.id, impact: v.impact, n: v.nodes.length, help: v.help,
    sample: v.nodes.slice(0, 3).map(x => x.target.join(' ') + ' :: ' + (x.failureSummary || '').slice(0, 160))}));
}
