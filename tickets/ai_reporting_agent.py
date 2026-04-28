from statistics import mean


class ReportingAIAgent:
    """Generates plain-language reporting insights from ticket aggregates."""

    def analyze(self, *, total, solved, pending, time_taken, no_response, solve_rate,
                tech_report, branch_report, issue_report, daily_values):
        insights = []
        recommendations = []

        if total == 0:
            return {
                'headline': 'No ticket data in the selected period.',
                'insights': ['Try expanding the date range to generate AI insights.'],
                'recommendations': ['Select a wider report window and regenerate the report.'],
                'health': 'neutral',
            }

        # Status mix
        pending_pct = round((pending / total) * 100, 1) if total else 0
        no_response_pct = round((no_response / total) * 100, 1) if total else 0
        insights.append(f'Solve rate is {solve_rate}% with {pending_pct}% still pending.')

        if no_response_pct > 20:
            insights.append(f'No-response tickets are high at {no_response_pct}%.')
            recommendations.append('Review no-response tickets first and enforce follow-up SLAs.')

        # Top issue signal
        if issue_report:
            top_issue = issue_report[0]
            issue_share = round((top_issue['total'] / total) * 100, 1)
            insights.append(
                f'Top issue is "{top_issue["issue"]}" with {top_issue["total"]} tickets ({issue_share}%).'
            )
            if issue_share >= 30:
                recommendations.append('Create a focused action plan for the top repeating issue.')

        # Technician and branch effectiveness
        if tech_report:
            best_tech = max(tech_report, key=lambda r: (r['solved_count'] / r['total']) if r['total'] else 0)
            best_rate = round((best_tech['solved_count'] / best_tech['total']) * 100, 1) if best_tech['total'] else 0
            insights.append(f'Best technician closure rate: {best_tech["technician_name"]} ({best_rate}%).')

        if branch_report:
            busiest_branch = max(branch_report, key=lambda r: r['total'])
            insights.append(f'Busiest branch: {busiest_branch["branch"]} ({busiest_branch["total"]} tickets).')

        # Daily trend signal
        if len(daily_values) >= 3:
            recent = daily_values[-3:]
            recent_avg = mean(recent)
            overall_avg = mean(daily_values)
            if recent_avg > overall_avg * 1.2:
                insights.append('Recent ticket volume is rising above the overall average.')
                recommendations.append('Consider temporary staffing boost for current ticket load.')
            elif recent_avg < overall_avg * 0.8:
                insights.append('Recent ticket volume is lower than the overall average.')

        if solve_rate < 60:
            health = 'critical'
            recommendations.append('Prioritize pending backlog reduction to improve solve rate.')
        elif solve_rate < 80:
            health = 'warning'
            recommendations.append('Target daily closure goals to push solve rate above 80%.')
        else:
            health = 'good'

        if not recommendations:
            recommendations.append('Maintain current workflow and monitor daily trend changes.')

        return {
            'headline': f'AI summary: {solved} solved out of {total} total tickets.',
            'insights': insights[:5],
            'recommendations': recommendations[:4],
            'health': health,
        }
