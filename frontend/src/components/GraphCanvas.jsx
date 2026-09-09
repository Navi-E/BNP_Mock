import React, { useEffect, useRef } from "react";
import cytoscape from "cytoscape";

export default function GraphCanvas({ elements, onNodeSelect }) {
    const containerRef = useRef(null);
    const cyRef = useRef(null);

    useEffect(() => {
        if (!containerRef.current) return;

        if (cyRef.current) {
            cyRef.current.destroy();
            cyRef.current = null;
        }

        const cy = cytoscape({
            container: containerRef.current,
            elements: elements,
            style: [
                {
                    selector: "node",
                    style: {
                        label: "data(label)",
                        color: "#e2e8f0",
                        "font-size": "10px",
                        "font-weight": 600,
                        "text-valign": "bottom",
                        "text-margin-y": 6,
                        width: 38,
                        height: 38,
                        "background-color": "#3b82f6",
                        "border-width": 2,
                        "border-color": "#070b13"
                    }
                },
                {
                    selector: "node[risk >= 70]",
                    style: {
                        "background-color": "#ef4444",
                        "border-color": "#fca5a5",
                        "border-width": 3,
                        width: 46,
                        height: 46
                    }
                },
                {
                    selector: "node[risk >= 40][risk < 70]",
                    style: {
                        "background-color": "#f59e0b",
                        "border-color": "#fde68a"
                    }
                },
                {
                    selector: "node[risk < 40]",
                    style: {
                        "background-color": "#10b981",
                        "border-color": "#6ee7b7"
                    }
                },
                {
                    selector: "edge",
                    style: {
                        width: 2,
                        "line-color": "#475569",
                        "target-arrow-color": "#475569",
                        "target-arrow-shape": "triangle",
                        "curve-style": "bezier",
                        label: "data(amount)",
                        "font-size": "9px",
                        color: "#94a3b8",
                        "text-rotation": "autorotate",
                        "text-margin-y": -8
                    }
                },
                {
                    selector: "edge[isLaundering = 1]",
                    style: {
                        "line-color": "#ef4444",
                        "target-arrow-color": "#ef4444",
                        width: 3
                    }
                }
            ],
            layout: {
                name: "cose",
                animate: false,
                padding: 60,
                nodeRepulsion: 12000,
                idealEdgeLength: 100
            }
        });

        cyRef.current = cy;

        cy.on("tap", "node", (evt) => {
            if (onNodeSelect) {
                onNodeSelect(evt.target.data());
            }
        });

        return () => {
            if (cyRef.current) {
                cyRef.current.destroy();
                cyRef.current = null;
            }
        };
    }, [elements, onNodeSelect]);

    return (
        <div className="graph-stage">
            <div id="cy-container" ref={containerRef} />
        </div>
    );
}