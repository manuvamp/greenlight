import { Link } from "react-router-dom";
import { Empty } from "../components/ui";

export function NotFound() {
  return (
    <div className="container page">
      <div className="panel">
        <Empty icon="alert" title="Page not found">
          Nothing lives at this address. <Link to="/">Back to the replays</Link>.
        </Empty>
      </div>
    </div>
  );
}
