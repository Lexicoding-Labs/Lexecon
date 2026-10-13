import React, { useState } from 'react';
import { AuthAPI, DecisionAPI, PolicyAPI } from '../api/endpoints';

type Result = { permit: string; deny: string; responsesVerified: boolean };

export default function GuidedExample({ onComplete }: { onComplete: () => Promise<void> }) {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Result | null>(null);

  const run = async () => {
    setWorking(true);
    setError('');
    setResult(null);
    try {
      const [identity, current] = await Promise.all([AuthAPI.me(), PolicyAPI.status()]);
      const user = identity.data?.user;
      if (user?.role !== 'admin') throw new Error('Only a local administrator can load the example policy.');
      if ((current.data?.terms_count || 0) + (current.data?.relations_count || 0) > 0 &&
          !window.confirm('This example replaces the policy currently loaded in memory. Continue?')) return;

      await PolicyAPI.load({ relations: [
        { type: 'permits', subject: `actor:${user.username}`, action: 'action:read' },
        { type: 'permits', subject: `actor:${user.username}`, action: 'tool:safe_demo' },
      ] });
      const common = {
        actor: user.username, tool: 'safe_demo',
        user_intent: 'Local guided policy example', context: { demo: true },
      };
      const allowed = (await DecisionAPI.decide({ ...common, proposed_action: 'read' })).data;
      const allowedCheck = (await DecisionAPI.verify(allowed)).data;
      const denied = (await DecisionAPI.decide({ ...common, proposed_action: 'delete' })).data;
      const deniedCheck = (await DecisionAPI.verify(denied)).data;
      if (allowed.decision !== 'permit' || denied.decision !== 'deny') {
        throw new Error(`Unexpected policy results: read=${allowed.decision}, delete=${denied.decision}. Check the loaded policy.`);
      }
      setResult({
        permit: allowed.decision,
        deny: denied.decision,
        responsesVerified: allowedCheck.verified === true && deniedCheck.verified === true,
      });
      await onComplete();
    } catch (e: any) {
      setError(e?.message || 'The example could not complete.');
      await onComplete();
    } finally {
      setWorking(false);
    }
  };

  return (
    <section aria-label="Guided decision example" className="stipple-guided">
      <div className="stipple-guided-copy">
        <div className="stipple-eyebrow">Try the workflow</div>
        <h2>Run a policy example</h2>
        <p>Load an in-memory policy, request a permitted read and a denied delete, then compare both responses with ledger records. No tool executes.</p>
        {error && <p role="alert" className="stipple-notice stipple-notice-error">Example failed: {error}</p>}
        {result && <p role="status" className="stipple-guided-result">
          Policy result: <strong>{result.permit}</strong> for read, <strong>{result.deny}</strong> for delete.
          {' '}Response to ledger comparison: <strong>{result.responsesVerified ? 'passed' : 'failed'}</strong>.
          {' '}Verify Integrity checks the ledger chain separately.
        </p>}
      </div>
      <button className="stipple-button stipple-button-primary" type="button" disabled={working} onClick={run}>
        {working ? 'Running example…' : 'Run policy example'}
      </button>
    </section>
  );
}
