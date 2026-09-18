import type { Instance, Schedule } from "../types/scheduling";

export default function ScheduleTimeline({ instance, schedule }: { instance: Instance; schedule: Schedule }) {
  const weeks = Array.from({ length: Math.max(instance.horizon_weeks, ...schedule.accesses.map(a => a.week)) }, (_, index) => index + 1);
  const lookup = new Map(schedule.accesses.map(a => [`${a.activity_id}:${a.week}`, a]));
  return <div className="table-scroll"><table>
    <caption>Solver assignments; consult the reference validation report before using them.</caption>
    <thead><tr><th>Activity</th>{weeks.map(week => <th key={week}>W{week}</th>)}</tr></thead>
    <tbody>{instance.activities.map(activity => <tr key={activity.activity_id}>
      <th>{activity.activity_id}</th>{weeks.map(week => {
        const access = lookup.get(`${activity.activity_id}:${week}`);
        return <td key={week} className={access ? "timeline-access" : ""} title={access ? `Access ${access.access_night}${access.eclo ? "; ECLO" : ""}` : "No access"}>
          {access ? access.eclo ? "E" : "●" : "—"}
        </td>;
      })}
    </tr>)}</tbody>
  </table></div>;
}
