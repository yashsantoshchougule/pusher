import React from 'react';

export default function TermsPage() {
  return (
    <main className="mx-auto w-[min(90%,42rem)] space-y-4 py-8">
      <h1 className="text-2xl font-bold">Pusher Terms &amp; Conditions</h1>
      <section className="space-y-1">
        <h2 className="text-lg font-semibold">Authorized use</h2>
        <p>Use Pusher only on systems you own or have explicit written permission to test. Stay within the authorized targets, time windows, traffic limits, and credentials.</p>
      </section>
      <section className="space-y-1">
        <h2 className="text-lg font-semibold">Running tests</h2>
        <p>Set a traffic budget appropriate for the target. Monitor the run and stop it if it causes unexpected errors or affects other users. Follow the target operator’s rules for staging and production.</p>
      </section>
      <section className="space-y-1">
        <h2 className="text-lg font-semibold">Accounts and test data</h2>
        <p>Keep account and target credentials private. Use disposable test data where possible, and review exports before sharing them. Pusher stores profiles, configuration, and run reports in its backend database.</p>
      </section>
      <section className="space-y-1">
        <h2 className="text-lg font-semibold">Interpreting results</h2>
        <p>Results describe the measured workload and environment. They can vary with the host, network, configuration, and target behavior.</p>
      </section>
      <a className="underline" href="/">Return to Pusher</a>
    </main>
  );
}
