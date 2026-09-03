"""Render Wikipedia template markup from ordered fields."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TemplateField:
    """One ordered field in a Wikipedia template."""

    name: str
    value: object = ""

    def rendered_value(self) -> str:
        """Return the field value as wiki text, preserving blank strings."""
        return "" if self.value is None else str(self.value)


FieldInput = TemplateField | tuple[str, object] | Mapping[str, object]


def render_template(
    template_name: str,
    fields: Iterable[FieldInput],
    *,
    add_param_space: bool = False,
    vertical: bool = False,
) -> str:
    """Render a Wikipedia template with fields in the supplied order.

    By default this mirrors the compact Perl output style:
    ``{{cite book |isbn=...}}``. With ``add_param_space`` it pads around
    the equals sign and field separators. With ``vertical`` each parameter
    is emitted on its own line.
    """
    normalized_fields = [_coerce_field(field) for field in fields]
    if vertical:
        return _render_vertical(
            template_name,
            normalized_fields,
            add_param_space=add_param_space,
        )
    return _render_inline(template_name, normalized_fields, add_param_space=add_param_space)


def _coerce_field(field: FieldInput) -> TemplateField:
    if isinstance(field, TemplateField):
        return field
    if isinstance(field, Mapping):
        return TemplateField(str(field["name"]), field.get("value", ""))
    name, value = field
    return TemplateField(str(name), value)


def _render_inline(
    template_name: str,
    fields: Iterable[TemplateField],
    *,
    add_param_space: bool,
) -> str:
    field_list = list(fields)
    if add_param_space:
        rendered_fields = []
        for index, field in enumerate(field_list):
            value = field.rendered_value()
            if value or index == len(field_list) - 1:
                rendered_fields.append(f" | {field.name} = {value}")
            else:
                rendered_fields.append(f" | {field.name} =")
    else:
        rendered_fields = [f" |{field.name}={field.rendered_value()}" for field in field_list]
    return "{{" + template_name + "".join(rendered_fields) + "}}"


def _render_vertical(
    template_name: str,
    fields: Iterable[TemplateField],
    *,
    add_param_space: bool,
) -> str:
    if add_param_space:
        rendered_fields = [f"| {field.name} = {field.rendered_value()}" for field in fields]
    else:
        rendered_fields = [f"|{field.name}={field.rendered_value()}" for field in fields]
    return "\n".join(["{{" + template_name, *rendered_fields, "}}"])


def fields_from_mapping(fields: Mapping[str, Any]) -> list[TemplateField]:
    """Convert an insertion-ordered mapping into template fields."""
    return [TemplateField(name, value) for name, value in fields.items()]
