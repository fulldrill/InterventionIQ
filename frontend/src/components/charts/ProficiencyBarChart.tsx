"use client";
/**
 * ProficiencyBarChart
 * Renders class proficiency by CCSS standard as a horizontal bar chart.
 * Standards below threshold shown in red; above in green.
 * Suppressed groups (N < 5) shown with a dashed pattern and tooltip.
 */
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { PROFICIENCY_THRESHOLD_PCT } from "@/lib/constants";

interface StandardData {
  standard: string;
  proficiency: number;
  student_count: number;
  suppressed: boolean;
}

interface Props {
  data: StandardData[];
  height?: number;
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload as StandardData;
    return (
      <div className="bg-white border border-gray-200 rounded shadow p-3 text-sm">
        <p className="font-semibold text-gray-800">{d.standard}</p>
        {d.suppressed ? (
          <p className="text-gray-500 italic">N&lt;5 — data suppressed to protect privacy</p>
        ) : (
          <>
            <p className="text-gray-700">Proficiency: <span className="font-medium">{d.proficiency}%</span></p>
            <p className="text-gray-500">Students assessed: {d.student_count}</p>
          </>
        )}
      </div>
    );
  }
  return null;
};

export default function ProficiencyBarChart({ data, height = 400 }: Props) {
  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="standard"
            tick={{ fontSize: 11 }}
            width={115}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            x={PROFICIENCY_THRESHOLD_PCT}
            stroke="#F59E0B"
            strokeDasharray="5 5"
            label={{ value: `Target ${PROFICIENCY_THRESHOLD_PCT}%`, position: "top", fontSize: 11, fill: "#F59E0B" }}
          />
          <Bar dataKey="proficiency" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={
                  entry.suppressed
                    ? "#D1D5DB"
                    : entry.proficiency >= PROFICIENCY_THRESHOLD_PCT
                    ? "#10B981"
                    : entry.proficiency >= PROFICIENCY_THRESHOLD_PCT * 0.7
                    ? "#F59E0B"
                    : "#EF4444"
                }
                opacity={entry.suppressed ? 0.5 : 1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 justify-center">
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-500 rounded-sm inline-block" /> At or above target</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-yellow-400 rounded-sm inline-block" /> Approaching target</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-500 rounded-sm inline-block" /> Below target</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-gray-300 rounded-sm inline-block" /> N&lt;5 suppressed</span>
      </div>
    </div>
  );
}
