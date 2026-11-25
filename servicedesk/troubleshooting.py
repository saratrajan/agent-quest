"""Troubleshooting threads: what the people working an incident wrote down.

Each failure pattern has three diagnostics specific to it (CHECKS). Around
those, a thread is assembled the way a real one unfolds: the service desk
assigns it, an on-call engineer picks it up, a first guess is ruled out,
others add findings, the cause is named, a fix is applied and verified, and
the incident is closed with its root cause, fix and follow-up.
"""
import random
from datetime import timedelta

from servicedesk.catalog import REGIONS, SERVICES, SUPPLIERS

ERROR_CODES = ["HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "ERR_TIMEOUT", "ERR_CONN_RESET", "E4012", "E5031"]

CHECKS = {
    "search-stale-fares": [
        "Cache hit ratio on the fare cache is 99.7%, up from the usual 82%. Entries are being served far longer than they should be.",
        "Compared 20 fares in search against {supplier} directly: {pct}% differ, always older in our results. No errors in the search logs.",
        "Config history shows fare_cache_ttl_seconds changed from 300 to 21600 this morning."],
    "search-latency-capacity": [
        "Search pool CPU is at 96% on every node in {region}; request queue depth is growing by about 40 a second.",
        "Request volume is 2.1 times the same hour last week. Traffic is spread across normal user agents, so it does not look like abuse.",
        "Thread pool exhaustion warnings on all search nodes; downstream pricing calls are healthy at 40 ms."],
    "search-index-lag": [
        "Index holds about {pct}% fewer documents than the inventory table for the affected supplier.",
        "Indexing pipeline's last committed checkpoint is 14 hours old; the consumer is stuck retrying one message.",
        "The stuck message is a property record with a malformed geo field; every retry fails validation."],
    "search-empty-results-deploy": [
        "Search returns HTTP 200 with an empty list in 30 ms. Latency and error rate look perfect, which is why no alert fired on errors.",
        "Query parser log shows the filter clause being dropped: every query is sent to the index with no origin or destination.",
        "Diff of the release shows a rewrite of the filter builder; the old path is still deployed on one canary node, which returns results."],
    "flight-booking-5xx-deploy": [
        "Flight booking error rate went from 0.2% to {pct}% within two minutes; errors are {error_code} at the confirm step only.",
        "Stack traces all end in a null reference while building the passenger record, for passengers with no middle name.",
        "Bookings with a middle name succeed. The failing code path was added in today's release."],
    "flight-seatmap-timeout": [
        "Seat map calls to {supplier} are taking 20 to 30 seconds; other carriers answer in under 400 ms.",
        "Booking completion rate is unchanged; only the optional seat selection step is failing.",
        "Our adapter has not changed in three weeks. Timeouts began at the same minute across all regions."],
    "flight-double-ticketing": [
        "Found {pct} orders today with two ticket numbers for one passenger and one payment capture.",
        "In every case the first ticketing call took over 25 seconds and the client retried; both calls eventually succeeded at the airline.",
        "The retry path sends a fresh request id, so the airline cannot recognise it as the same request."],
    "flight-fare-rules-missing": [
        "The supplier response for the affected fare classes has no rules block at all; our page renders an empty panel.",
        "About {pct}% of fares from one airline are affected, all in two fare families.",
        "Sample responses from last month include the block under a different field name."],
    "hotel-supplier-429": [
        "{supplier} is answering availability calls with 429 Too Many Requests; our request rate to them is 2.3 times the contracted limit.",
        "The extra requests come from hotel detail pages hit by a single crawler cycling through dates.",
        "Other hotel suppliers are healthy, and our own services show no errors apart from this adapter."],
    "hotel-confirmation-delay": [
        "{pct} bookings are in awaiting-supplier state, the oldest for 3 hours. Payment has been captured on all of them.",
        "Our callback endpoint is healthy and has received nothing from {supplier} for these bookings.",
        "Polling the supplier by booking reference returns the booking as confirmed on their side."],
    "hotel-rate-mismatch": [
        "Listing price and checkout total differ by a fixed amount per night for {supplier} properties in {region}.",
        "The supplier feed now carries a resort_fee field that our rate mapper ignores.",
        "Cached rates for these properties predate the supplier's tax update."],
    "hotel-db-slow-queries": [
        "Write latency on the hotel bookings database is 2.4 seconds; CPU is pinned at 100% on the primary.",
        "Slow query log shows a full table scan on bookings by guest email, running every few seconds.",
        "The query comes from a back-office report added last week; the column has no index."],
    "cruise-cabin-double-booking": [
        "Two confirmed bookings exist for the same cabin on the same sailing; the second was sold 35 minutes after the first.",
        "Cabin inventory sync last ran 40 minutes before the second sale; our count still showed the cabin as free.",
        "{supplier} confirms they rejected the second booking at their end with an already-sold error."],
    "cruise-itinerary-images": [
        "Image requests on itinerary pages return 404 for about {pct}% of ports.",
        "The image path prefix in content settings was edited yesterday; old paths are still referenced in cached pages.",
        "Fetching an affected image with the new prefix works; the CDN is serving pages cached before the change."],
    "cruise-deposit-calc-deploy": [
        "Deposit shown on cruise bookings is {pct}% of the fare; the rule for these sailings says 20%.",
        "The deposit rule lookup returns the default rule for every sailing since today's cruise service release.",
        "The release renamed the sailing-category key used in the rule lookup; the rules table still uses the old name."],
    "payments-3ds-timeout": [
        "{pct}% of card payments stall at the 3-D Secure step; our payments service is healthy and waiting on the gateway.",
        "The primary gateway's status page shows degraded authentication since a few minutes before our first failure.",
        "Payments that do not require 3-D Secure are succeeding, so the problem is confined to the verification call."],
    "payments-duplicate-charge": [
        "Reconciliation shows two captures for one order on {pct} payments since the last payments release.",
        "Every duplicate follows a gateway response slower than 8 seconds; the new retry logic fires at 8 seconds.",
        "The retry creates a new capture and does not reuse the original idempotency key."],
    "payments-refund-backlog": [
        "Refund queue holds {pct} thousand items; the oldest was requested 9 days ago.",
        "Refund workers are processing at their fixed nightly limit with no errors.",
        "Inbound refund volume tripled after {supplier} cancelled a block of flights."],
    "payments-currency-rounding": [
        "Receipt totals differ from captured amounts by one minor unit, only in currencies with zero or three decimal places.",
        "About {pct} mismatches a day, starting the day after the currency settings update.",
        "The update changed the rounding mode from half-up to half-even."],
    "payments-db-connections": [
        "The payments database reports its maximum connection count reached; new connections are refused with {error_code}.",
        "A single client, the settlement job, holds over 300 idle-in-transaction connections.",
        "The settlement job has been running for 6 hours; it normally finishes in 20 minutes."],
    "identity-login-failures-cert": [
        "Sign-in success rate is under 1%. Downstream services reject every new token with a signature validation error.",
        "The token signing certificate expired at 00:00 UTC today.",
        "Sessions issued yesterday still work until they expire, which is why the failure rate crept up and did not jump."],
    "identity-token-expiry-config": [
        "Session refresh calls are 10 times the normal rate and about a third fail.",
        "Tokens issued since yesterday evening carry a 5-minute lifetime; the intended value is 60 minutes.",
        "Config history shows session_lifetime changed from 3600 to 300; the field is in seconds and the editor assumed minutes."],
    "identity-mfa-sms-delay": [
        "Text codes are taking 10 to 14 minutes to arrive in {region}; codes expire after 5.",
        "Our send requests are accepted by the SMS provider within a second; the delay is after hand-off.",
        "Email codes arrive normally. About {pct}% of affected customers have no email verification set up."],
    "notif-email-queue-backlog": [
        "Email queue depth is {pct} thousand; the oldest message is 3 hours old.",
        "A marketing send of 2 million messages started 4 hours ago on the same queue as booking confirmations.",
        "Workers are healthy and at full throughput; inbound volume is 5 times normal."],
    "notif-wrong-template-deploy": [
        "Booking emails sent since the release contain raw placeholder names in the greeting.",
        "About {pct}% of emails are affected: those using the new confirmation template.",
        "The release renamed a template variable in the template but not in the code that fills it."],
    "notif-sms-provider-outage": [
        "Every text message send is failing with {error_code} from the SMS provider.",
        "The provider's status page reports a major incident on their messaging platform.",
        "Email and push notifications are sending normally."],
    "pricing-stale-cache-deploy": [
        "Price-change events from suppliers are arriving but nothing is consuming them; the queue is growing.",
        "The cache invalidation consumer has not been running since this morning's pricing release.",
        "{pct}% of checkouts show a price different from search, across flights and hotels alike."],
    "pricing-currency-feed": [
        "The exchange rate table was last updated 26 hours ago.",
        "The feed job fails on every run with {error_code} while parsing the provider's file.",
        "The provider's file has a new header row and one extra column since yesterday."],
    "pricing-promo-misapplied": [
        "Average discount on orders using the new code is {pct}%; the promotion was meant to give 10%.",
        "The promotion is configured as stackable, so it combines with the member price.",
        "The code is being shared on social media; redemptions are 8 times the forecast."],
    "sync-gds-timeouts": [
        "Requests to {supplier} are timing out at {pct}%; average response time has gone from 300 ms to over 9 seconds.",
        "Every other supplier adapter is healthy from the same hosts, so our network is not the cause.",
        "The supplier's status page reports degraded performance in {region}."],
    "sync-inventory-lag": [
        "Inventory sync queue is {pct} thousand updates behind and growing.",
        "One supplier sent a full inventory refresh, about 40 times their usual volume.",
        "Sync consumers are at maximum throughput with no errors."],
    "sync-schema-change": [
        "Every update from {supplier} fails validation with {error_code}: unexpected date format.",
        "Failures began at 02:00 UTC, matching the supplier's release window.",
        "Dead-letter queue holds all rejected updates, so nothing is lost."],
    "sync-network-partition": [
        "All supplier adapters in {region} are failing to connect at once; other regions are healthy.",
        "Packet loss of {pct}% through the outbound gateway in that region.",
        "Network maintenance finished in that data centre 10 minutes before the first failure."],
    "web-checkout-js-error-deploy": [
        "Browser error tracking shows a script error on the checkout page in {pct}% of sessions since the web release.",
        "The payment form's submit handler is undefined: one script bundle is missing from the page.",
        "The mobile app, which does not use this bundle, is converting normally."],
    "web-cdn-stale-assets": [
        "Affected visitors receive the new page with last month's stylesheet.",
        "CDN cache rules were edited yesterday; the stylesheet now has a 30-day lifetime and no version in its name.",
        "About {pct}% of visitors are affected, those served from caches that held the old file."],
    "web-slow-pages": [
        "Time to first byte from {region} is over 3 seconds; from other regions it is under 300 ms.",
        "Origin servers answer in 80 ms; the delay is between the visitor and the CDN edge.",
        "The CDN provider reports congestion at a point of presence in that region."],
    "mobile-tls-cert-expired": [
        "TLS handshakes to the mobile gateway fail with {error_code}; app traffic is near zero.",
        "The gateway's certificate expired an hour ago; the website uses a different certificate and is unaffected.",
        "This certificate was issued by hand last year and was never added to expiry monitoring."],
    "mobile-rate-limit-misconfig": [
        "429 responses from the mobile gateway are 50 times the normal rate, spread across ordinary users.",
        "The per-user limit is set to {pct} requests a minute; the intended value is 600.",
        "The limit was changed in yesterday's gateway configuration update."],
    "mobile-old-app-version": [
        "Crash reports come only from one app release that is over a year old.",
        "{pct} reports this week, all on operating system versions we no longer test.",
        "Could not reproduce on the oldest device in the test lab."],
    "loyalty-points-not-credited": [
        "About {pct}% of bookings completed last week have no entry in the points ledger.",
        "Every missing booking was paid in two instalments.",
        "The nightly crediting job filters on a single payment record per booking."],
}

POOL = ["Asha Verma", "Tomás Ibarra", "Mei-Lin Zhou", "Jonas Eriksen", "Farah Haddad", "Kwame Osei", "Elena Petrova",
        "Diego Santoro", "Hana Kobayashi", "Luca Moretti", "Priya Nair", "Samuel Okafor", "Ingrid Larsen", "Mateo Rivas",
        "Yuki Tanaka", "Omar Farouk", "Clara Becker", "Rohan Mehta", "Nadia Rahman", "Pedro Alves", "Sofia Marchetti",
        "Daniel Kim", "Amara Diallo", "Viktor Novak"]
DESK = POOL[:3]
COMMANDERS = POOL[3:5]
SUPPORT = POOL[5:7]
SUPPLIER_DESK = POOL[7:9]
SRE = POOL[9:12]
ENGINEERS = {s.team: [POOL[12 + (k * 3 + j) % 12] for j in range(3)] for k, s in enumerate(SERVICES)}
NAMES = {s.id: s.name for s in SERVICES}
DEPENDS = {s.id: s.depends_on for s in SERVICES}

ACK = ["Acknowledged. Looking at the dashboards for {service}.",
       "Paged and online. Starting with the error rate and latency graphs for {service}.",
       "Picking this up. First checking what changed around {service} in the last few hours."]
CAUSE = {
    "bad-deploy": "a faulty release of {service}", "capacity": "{service} was under-provisioned for the load",
    "dependency-outage": "an outage at a provider that {service} depends on",
    "config-change": "a configuration change affecting {service}", "data-quality": "wrong or out-of-date data in {service}",
    "certificate-expiry": "an expired certificate on {service}",
    "supplier-api": "a fault or change in a supplier's interface used by {service}",
    "database": "a database problem under {service}", "network": "a network fault affecting {service}",
    "unknown": "not determined",
}
FOUND = {
    "bad-deploy": "Cause identified: the latest release. The timing matches and the failing code path is new in it.",
    "capacity": "Cause identified: demand is above what is provisioned. Nothing is broken; there is not enough of it.",
    "dependency-outage": "Cause identified: a provider we depend on is degraded. Our side is healthy and waiting on them.",
    "config-change": "Cause identified: a configuration change whose time matches the start of the problem.",
    "data-quality": "Cause identified: the data is wrong or stale. There are no errors because the system is doing what it was told.",
    "certificate-expiry": "Cause identified: a certificate past its expiry date.",
    "supplier-api": "Cause identified: the fault is on the supplier's side of the interface.",
    "database": "Cause identified: the database is the bottleneck, and one client is responsible.",
    "network": "Cause identified: a network fault. Unrelated destinations fail together from one location.",
    "unknown": "No cause found. Nothing in logs, metrics or recent changes explains it.",
}
FOLLOW = {
    "bad-deploy": "add a regression test for this path and hold releases at the canary stage for 15 minutes",
    "capacity": "review autoscaling limits and pre-scale before known peaks",
    "dependency-outage": "agree failover criteria with the provider and rehearse the fallback each quarter",
    "config-change": "require a second reviewer and a staged rollout for this setting",
    "data-quality": "add a reconciliation check and an alert when the two sides drift apart",
    "certificate-expiry": "bring every certificate under expiry monitoring with a 30-day warning",
    "supplier-api": "ask the supplier for advance notice of changes and add a contract test",
    "database": "review reporting queries before release and alert on connection count",
    "network": "add cross-region failover for this path",
    "unknown": "keep monitoring and reopen if it recurs",
}
VERIFY = ["Verified: error rate is back under 0.5% and has held for 20 minutes.",
          "Verified with a synthetic booking end to end. Graphs are back to baseline.",
          "Verified: three sample cases that were failing now succeed. Leaving the alert thresholds tightened for 24 hours.",
          "Verified against the original report. No new cases in the last 30 minutes."]
ADVICE = ["ask customers to retry in a few minutes", "take details and promise a call back", "offer booking by phone",
          "reassure customers that no money has been taken twice", "point customers to the status page"]
CLOSE = {"unknown": "Not reproducible", "dependency-outage": "Solved (workaround)", "supplier-api": "Solved (workaround)",
         "network": "Solved (workaround)"}


def _fill(rng: random.Random, template: str) -> str:
    return template.format(region=rng.choice(REGIONS), supplier=rng.choice(SUPPLIERS),
                           error_code=rng.choice(ERROR_CODES), pct=rng.randint(12, 85))


def _ruled_out(rng: random.Random, p) -> str:
    options = []
    if not p.deploy_related:
        options.append(f"Ruled out a bad release: no recent deploy to {p.service} lines up with the start of the problem.")
    if p.root_cause != "capacity":
        options.append(f"Ruled out capacity: CPU and memory on {p.service} are at normal levels.")
    if p.root_cause != "network":
        options.append("Ruled out the network: other services in the same region are healthy.")
    if p.root_cause != "database":
        options.append("Ruled out the database: query latency and connection count are normal.")
    for dep in DEPENDS[p.service]:
        if p.root_cause not in ("dependency-outage", "supplier-api") or dep != "supplier-sync":
            options.append(f"Ruled out {dep}: its error rate and latency are normal.")
    return rng.choice(options)


def _times(rng: random.Random, opened, resolved, n: int) -> list:
    """n strictly increasing times; the first shortly after opening, the last at resolution."""
    total = int((resolved - opened).total_seconds())
    offsets = sorted(int((0.01 + 0.9 * rng.random() ** 1.4) * total) for _ in range(n - 1))
    offsets[0] = min(offsets[0], rng.randint(120, 600), total // 4)
    for k in range(1, n - 1):
        offsets[k] = max(offsets[k], offsets[k - 1] + 20)
    overshoot = offsets[-1] - (total - 20) if n > 1 else 0
    if overshoot > 0:  # squeeze back inside the window, keeping the order and the gaps
        offsets = [max(20 * (k + 1), o - overshoot) for k, o in enumerate(offsets)]
        for k in range(1, n - 1):
            offsets[k] = max(offsets[k], offsets[k - 1] + 20)
    return [opened + timedelta(seconds=o) for o in offsets] + [resolved]


def build_thread(r: dict, seed: int) -> tuple[list[dict], str, str]:
    """Returns (notes, resolution, close_code) for one incident record."""
    rng = random.Random(f"{seed}/{r['number']}")
    p, pr = r["pattern"], r["priority"]
    service = NAMES[p.service]
    lead, second, third = rng.sample(ENGINEERS[r["team"]], 3)
    desk, on_call = rng.choice(DESK), f"{r['team']} on-call"
    notes: list[tuple[str, str, str]] = [
        ("Service desk", desk, f"Assigned to {r['team']}. Opened as P{r['at_open']} from a {r['source']} report.")]

    if r["parent"]:
        parent = r["parent"]["number"]
        minutes = int((r["opened"] - r["parent"]["opened"]).total_seconds() // 60)
        notes.append((on_call, lead, f"Symptoms match {parent}, opened {minutes} minutes earlier. Same service, same failure."))
        notes.append(("Service desk", desk, f"Linked as a duplicate. Reporter told to follow {parent} for updates."))
        resolution = f"Duplicate of {parent}. Resolved with the parent incident."
        notes.append((on_call, lead, resolution))
        code = "Duplicate"
    else:
        if r["vague"]:
            notes.append(("Service desk", desk, "The description is too thin to act on. Asked the reporter which product is "
                          "affected, for one example, and when it started."))
            who = "Monitoring" if r["source"] in ("monitoring", "synthetic-check") else rng.choice(POOL)
            notes.append(("Reporter", who, "More detail: " + _fill(rng, rng.choice(p.short_templates)) + ". "
                          + _fill(rng, rng.choice(p.description_templates)).split(". ")[0] + "."))
        notes.append((on_call, lead, rng.choice(ACK).format(service=service)))
        if r["at_open"] != pr:
            why = ("impact is wider than first reported" if pr < r["at_open"]
                   else "impact is limited and customers have a workaround")
            notes.append((on_call, lead, f"Changing priority from P{r['at_open']} to P{pr}: {why}."))
        commander = rng.choice(COMMANDERS)
        if pr == 1:
            notes.append(("Incident commander", commander, f"Major incident declared. Bridge is open; {lead} is technical "
                          "lead. Updates every 30 minutes."))
        elif pr == 2:
            notes.append(("Incident commander", commander, f"Coordinating. No bridge yet; {lead} leads. Updates hourly."))
        checks = [_fill(rng, c) for c in CHECKS[p.id]]
        notes.append((on_call, lead, checks[0]))
        notes.append((on_call if rng.random() < 0.6 else "Site reliability",
                      second if rng.random() < 0.5 else rng.choice(SRE), _ruled_out(rng, p)))
        notes.append((on_call, second, checks[1]))
        if pr <= 2 or (pr == 3 and rng.random() < 0.5):
            lo, hi = {1: (120, 900), 2: (30, 200), 3: (5, 40)}[pr]
            notes.append(("Customer support", rng.choice(SUPPORT), f"{rng.randint(lo, hi)} customer contacts so far. Holding "
                          f"message published; agents are told to {rng.choice(ADVICE)}."))
        if p.root_cause == "supplier-api":
            notes.append(("Supplier relations", rng.choice(SUPPLIER_DESK), f"Raised with the supplier's operations desk, their "
                          f"reference SR-{rng.randint(100000, 999999)}. They acknowledge a problem on their side."))
        if pr <= 2 or rng.random() < 0.6:
            notes.append(("Site reliability" if rng.random() < 0.4 else on_call, third, checks[2]))
        notes.append((on_call, lead, FOUND[p.root_cause]))
        notes.append((on_call, lead, "Applying the fix. " + r["fix"]))
        if pr <= 2:
            notes.append(("Incident commander", commander, "Mitigation is in place and metrics are recovering. Watching for "
                          "30 minutes before standing down."))
        else:
            notes.append((on_call, second, rng.choice(VERIFY)))
        cause = CAUSE[p.root_cause].format(service=service)
        resolution = (f"Root cause: {cause}. Fix: {r['fix']} Follow-up: {FOLLOW[p.root_cause]} "
                      f"(PRB{rng.randint(1000, 9999):07d}).")
        notes.append((on_call, lead, resolution))
        code = CLOSE.get(p.root_cause, "Solved (permanently)")

    stamps = _times(rng, r["opened"], r["resolved"], len(notes))
    out = [{"at": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "author": author, "role": role, "text": text}
           for t, (role, author, text) in zip(stamps, notes)]
    return out, resolution, code
