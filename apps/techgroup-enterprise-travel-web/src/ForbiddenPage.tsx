import { Link } from 'react-router-dom';

export default function ForbiddenPage() {
  return (
    <div className="page">
      <header>
        <h1>403 Forbidden</h1>
        <p>Your session is missing or invalid.</p>
      </header>
      <main className="layout single">
        <section className="panel">
          <p>Please sign in again with a valid token.</p>
          <Link to="/login">Go to Login</Link>
        </section>
      </main>
    </div>
  );
}
