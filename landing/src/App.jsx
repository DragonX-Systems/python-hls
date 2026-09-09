import "./App.css";

const repositoryUrl = "https://github.com/missionfission/hls-python";

const kernels = [
  ["GCD", "Control flow and refactor validation", "RTL verified"],
  ["FIR filter", "Signal and feed-handler pipelines", "Available"],
  ["Dot product", "Latency-sensitive arithmetic", "Available"],
  ["EMA", "Streaming indicators", "RTL verified"],
  ["FFT", "Spectral analysis", "Available"],
  ["Covariance", "Risk and factor calculations", "Available"],
];

function CodeBlock({ children }) {
  return (
    <pre className="code-block">
      <code>{children}</code>
    </pre>
  );
}

function App() {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="site-header">
        <nav className="nav" aria-label="Primary navigation">
          <a className="wordmark" href="#top" aria-label="Python-HLS home">
            python-hls
          </a>
          <div className="nav-links">
            <a href="#capabilities">Capabilities</a>
            <a href="#examples">Examples</a>
            <a className="nav-contact" href={repositoryUrl}>
              GitHub <span aria-hidden="true">↗</span>
            </a>
          </div>
        </nav>
      </header>
      <main id="main-content">
        <section id="top" className="hero section">
          <p className="eyebrow">Source available from DragonX Systems</p>
          <h1>
            Make hardware intent <em>explicit.</em>
          </h1>
          <p className="hero-copy">
            Python-HLS is an experimental project for turning supported Python
            kernels into inspectable hardware artifacts. Explore trading,
            data-science, and ML kernels with scheduling, resource allocation,
            verification, and technology-node estimates before a design reaches
            synthesis.
          </p>
          <div className="hero-actions">
            <a
              className="button button-primary"
              href={`${repositoryUrl}#readme`}
            >
              Read the documentation <span aria-hidden="true">↗</span>
            </a>
            <a className="button button-secondary" href="#capabilities">
              Explore capabilities
            </a>
          </div>
          <dl className="hero-facts" aria-label="Product highlights">
            <div>
              <dt>Input</dt>
              <dd>Supported Python subset</dd>
            </div>
            <div>
              <dt>Output</dt>
              <dd>Verilog or VHDL</dd>
            </div>
            <div>
              <dt>Access</dt>
              <dd>Noncommercial</dd>
            </div>
          </dl>
        </section>
        <section className="section section-wide" aria-labelledby="why-title">
          <p className="eyebrow">Why it exists</p>
          <h2 id="why-title">HLS needs a contract you can inspect.</h2>
          <p className="section-intro">
            In latency-sensitive systems, a small source change can have a large
            hardware consequence. Python-HLS keeps the compiler pipeline visible
            so teams can inspect the resulting schedule, allocation, and
            generated HDL before a change moves downstream.
          </p>
          <div className="card-grid">
            <article className="card">
              <h3>Understand the schedule</h3>
              <p>
                Explore ASAP, ALAP, and list scheduling rather than treating
                timing as an opaque artifact.
              </p>
            </article>
            <article className="card">
              <h3>Measure trade-offs</h3>
              <p>
                Compare estimated area, power, energy, latency, and
                critical-path metrics across technology nodes.
              </p>
            </article>
            <article className="card">
              <h3>Check the result</h3>
              <p>
                Generate testbenches and compare Python and RTL behavior as part
                of a verification workflow.
              </p>
            </article>
          </div>
        </section>
        <section
          id="capabilities"
          className="section"
          aria-labelledby="capabilities-title"
        >
          <p className="eyebrow">Compiler pipeline</p>
          <h2 id="capabilities-title">From source to hardware artifacts.</h2>
          <ol className="pipeline">
            <li>
              <span>01</span>
              <div>
                <h3>Parse &amp; lower</h3>
                <p>
                  Build an intermediate representation from supported Python
                  constructs.
                </p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <h3>Schedule &amp; allocate</h3>
                <p>
                  Apply scheduling and resource-allocation strategies, then
                  inspect their effects.
                </p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <h3>Generate &amp; verify</h3>
                <p>
                  Emit Verilog or VHDL, create testbenches, and run
                  equivalence-oriented checks.
                </p>
              </div>
            </li>
          </ol>
        </section>
        <section
          id="examples"
          className="section section-wide"
          aria-labelledby="examples-title"
        >
          <p className="eyebrow">Validated workloads</p>
          <h2 id="examples-title">Representative kernels across domains.</h2>
          <p className="section-intro">
            The repository includes focused workloads spanning trading signals,
            scientific computing, data science, and ML-oriented linear algebra.
          </p>
          <div className="kernel-grid">
            {kernels.map(([name, description, status]) => (
              <article className="kernel" key={name}>
                <div>
                  <h3>{name}</h3>
                  <p>{description}</p>
                </div>
                <span
                  className={
                    status === "RTL verified"
                      ? "status status-verified"
                      : "status"
                  }
                >
                  {status}
                </span>
              </article>
            ))}
          </div>
        </section>
        <section
          id="get-started"
          className="section getting-started"
          aria-labelledby="start-title"
        >
          <p className="eyebrow">Get started</p>
          <h2 id="start-title">Start with a kernel. Inspect the artifacts.</h2>
          <p className="section-intro">
            Use the included examples to review generated schedules, resource
            allocation, HDL, and available verification results.
          </p>
          <CodeBlock>
            {
              "Python source → intermediate representation → scheduled datapath\n→ resource allocation → Verilog / VHDL → verification artifacts"
            }
          </CodeBlock>
          <div className="callout">
            <strong>Important</strong>
            <p>
              Python-HLS is evaluated against a defined supported subset.
              Generated HDL, timing, and functional behavior should be
              independently reviewed and verified before production use.
            </p>
          </div>
          <div className="hero-actions">
            <a className="button button-primary" href={repositoryUrl}>
              View the source <span aria-hidden="true">↗</span>
            </a>
            <a
              className="button button-secondary"
              href={`${repositoryUrl}/blob/main/docs/TRADING_QUICKSTART.md`}
            >
              Read the quickstart <span aria-hidden="true">↗</span>
            </a>
          </div>
        </section>
      </main>
      <footer className="site-footer">
        <p>Python-HLS · A source-available DragonX Systems project</p>
        <a href={repositoryUrl}>
          GitHub <span aria-hidden="true">↗</span>
        </a>
      </footer>
    </>
  );
}

export default App;
