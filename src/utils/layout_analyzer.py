import schemdraw
from schemdraw.elements.elements import BBox

class LayoutAnalyzer:
    """
    Analyzes a schemdraw.Drawing object for layout issues like overlaps and messy wiring.
    """
    def __init__(self, drawing: schemdraw.Drawing, config: dict):
        self.drawing = drawing
        self.config = config
        self.issues = []

    def _get_element_id(self, element, index) -> str:
        """Creates a human-readable ID for an element."""
        # Labels are attached to other elements, so we describe them that way
        if isinstance(element, schemdraw.elements.lines.Label):
            # Find the element this label is attached to
            parent_id = f"Element_{element._attach_to_element_index}"
            return f"Label '{element.text}' (attached to {parent_id})"
        return f"{type(element).__name__}_{index}"

    def _bboxes_overlap(self, bbox1: BBox, bbox2: BBox) -> bool:
        """Checks if two bounding boxes overlap."""
        # Add a tiny margin to avoid flagging elements that just touch
        margin = 1e-6
        return not (bbox1.xmax < bbox2.xmin + margin or
                    bbox1.xmin > bbox2.xmax - margin or
                    bbox1.ymax < bbox2.ymin + margin or
                    bbox1.ymin > bbox2.ymax - margin)

    def run_all_checks(self) -> list:
        """Runs all layout checks and returns a list of found issues."""
        self.issues = []
        self._check_overlaps()
        self._check_wiring()
        return self.issues

    def _check_overlaps(self):
        """Detects overlapping elements or labels."""
        elements_with_bbox = []
        for i, element in enumerate(self.drawing.elements):
            try:
                # Add element index to the element object for later reference in _get_element_id
                element._element_index = i 
                bbox = element.get_bbox()
                elements_with_bbox.append({'element': element, 'bbox': bbox, 'id': self._get_element_id(element, i)})
            except Exception:
                continue # Some elements might not have a bbox

        for i in range(len(elements_with_bbox)):
            for j in range(i + 1, len(elements_with_bbox)):
                item1 = elements_with_bbox[i]
                item2 = elements_with_bbox[j]
                
                # Link label to its parent element for better reporting
                if isinstance(item1['element'], schemdraw.elements.lines.Label):
                    item1['element']._attach_to_element_index = item2['element']._element_index
                if isinstance(item2['element'], schemdraw.elements.lines.Label):
                    item2['element']._attach_to_element_index = item1['element']._element_index

                if self._bboxes_overlap(item1['bbox'], item2['bbox']):
                    # Don't report a label overlapping with its direct parent element
                    if (isinstance(item1['element'], schemdraw.elements.lines.Label) and item1['element']._attach_to == item2['element']) or \
                       (isinstance(item2['element'], schemdraw.elements.lines.Label) and item2['element']._attach_to == item1['element']):
                        continue
                    
                    self.issues.append({
                        'type': 'Overlap',
                        'elements': [item1['id'], item2['id']],
                        'details': f"Element '{item1['id']}' is overlapping with '{item2['id']}'."
                    })

    def _check_wiring(self):
        """Detects non-orthogonal (diagonal) lines if configured."""
        if self.config.get('allow_diagonal_lines', True):
            return

        for i, element in enumerate(self.drawing.elements):
            if isinstance(element, schemdraw.elements.lines.Line):
                # Use a small tolerance for floating point comparisons
                tolerance = 1e-9
                is_horizontal = abs(element.start.y - element.end.y) < tolerance
                is_vertical = abs(element.start.x - element.end.x) < tolerance
                
                if not is_horizontal and not is_vertical:
                    self.issues.append({
                        'type': 'Wiring',
                        'elements': [self._get_element_id(element, i)],
                        'details': f"The line from {element.start.round(2)} to {element.end.round(2)} is diagonal. Use orthogonal lines for clarity."
                    })

    def generate_report(self) -> str:
        """Generates a structured, LLM-friendly report of all found issues."""
        if not self.issues:
            return "No layout issues found."

        report = "**[Layout Analysis Report]**\n\n"
        report += "Your generated code is syntactically correct, but it has the following layout violations that must be fixed:\n\n"
        
        for i, issue in enumerate(self.issues):
            report += f"**Issue #{i+1}: {issue['type']} Violation**\n"
            report += f"- **Details**: {issue['details']}\n"
            if issue['type'] == 'Overlap':
                report += "- **Suggestion**: Modify the position of one of the elements using `.at()`, or for labels, add a `loc` (e.g., `'top'`) or `offset` parameter.\n\n"
            elif issue['type'] == 'Wiring':
                report += "- **Suggestion**: Replace the single diagonal line with two orthogonal lines using methods like `.tox()` or `.toy()` to create a clean 90-degree turn.\n\n"
        
        return report