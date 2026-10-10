from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Constituent(BaseModel):

    model_config = ConfigDict(extra="allow")

    constituentID: int
    role: str = ""
    name: str = ""
    constituentULAN_URL: str = ""
    constituentWikidata_URL: str = ""
    gender: str = ""


class Tag(BaseModel):

    model_config = ConfigDict(extra="allow")

    term: str
    AAT_URL: Optional[str] = None
    Wikidata_URL: Optional[str] = None


class MetObject(BaseModel):

    model_config = ConfigDict(extra="allow")

    objectID: int = Field(gt=0)
    isHighlight: bool
    isPublicDomain: bool
    title: str
    department: str
    objectURL: str
    objectBeginDate: int
    objectEndDate: int

    accessionNumber: str = ""
    accessionYear: str = ""
    primaryImage: str = ""
    primaryImageSmall: str = ""
    additionalImages: List[str] = Field(default_factory=list)
    constituents: Optional[List[Constituent]] = None
    objectName: str = ""
    culture: str = ""
    period: str = ""
    dynasty: str = ""
    reign: str = ""
    portfolio: str = ""
    artistRole: str = ""
    artistPrefix: str = ""
    artistDisplayName: str = ""
    artistDisplayBio: str = ""
    artistSuffix: str = ""
    artistAlphaSort: str = ""
    artistNationality: str = ""
    artistBeginDate: str = ""
    artistEndDate: str = ""
    artistGender: str = ""
    artistWikidata_URL: str = ""
    artistULAN_URL: str = ""
    objectDate: str = ""
    medium: str = ""
    dimensions: str = ""
    creditLine: str = ""
    geographyType: str = ""
    city: str = ""
    state: str = ""
    county: str = ""
    country: str = ""
    region: str = ""
    subregion: str = ""
    locale: str = ""
    locus: str = ""
    excavation: str = ""
    river: str = ""
    classification: str = ""
    rightsAndReproduction: str = ""
    linkResource: str = ""
    metadataDate: str = ""
    repository: str = ""
    tags: Optional[List[Tag]] = None
    objectWikidata_URL: str = ""
    isTimelineWork: bool = False
    GalleryNumber: str = ""

    @field_validator("objectURL")
    @classmethod
    def check_object_url(cls, value: str) -> str:
        if not value.startswith("https://www.metmuseum.org/"):
            raise ValueError(f"objectURL должен вести на сайт музея, получено: {value}")
        return value

    @field_validator("title", "department")
    @classmethod
    def check_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("поле не должно быть пустым")
        return value


class ObjectIDsResponse(BaseModel):

    total: int = Field(ge=0)
    objectIDs: Optional[List[int]] = None

    @property
    def ids(self) -> List[int]:
        return self.objectIDs or []

    @model_validator(mode="after")
    def check_ids(self):
        if any(object_id <= 0 for object_id in self.ids):
            raise ValueError("objectIDs должны быть положительными числами")
        return self


class ObjectsListResponse(ObjectIDsResponse):

    @model_validator(mode="after")
    def check_total(self):
        if self.total != len(self.ids):
            raise ValueError(f"total={self.total}, а в objectIDs {len(self.ids)} элементов")
        return self


class SearchResponse(ObjectIDsResponse):

    @model_validator(mode="after")
    def check_page_size(self):
        if len(self.ids) > self.total:
            raise ValueError(f"на странице {len(self.ids)} ID, а всего найдено {self.total}")
        return self


class RetiredEndpointResponse(BaseModel):

    message: str
    replacement: str
    documentation: str


class Department(BaseModel):
    departmentId: int = Field(gt=0)
    displayName: str = Field(min_length=1)


class DepartmentsResponse(BaseModel):

    departments: List[Department]


class ErrorResponse(BaseModel):

    message: str
