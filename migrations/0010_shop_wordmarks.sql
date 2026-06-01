ALTER TABLE shops ADD COLUMN wordmark_text TEXT NOT NULL DEFAULT '';
ALTER TABLE shops ADD COLUMN wordmark_style TEXT NOT NULL DEFAULT '';

UPDATE shops
SET wordmark_text = 'morceau',
    wordmark_style = 'lowercase'
WHERE slug = 'morceau';

UPDATE shops
SET wordmark_text = 'SHOWROOM MONTRÉAL',
    wordmark_style = 'wide_caps'
WHERE slug = 'showroom-montreal';

UPDATE shops
SET wordmark_text = 'MONTRÉAL MØDERNE',
    wordmark_style = 'wide_caps'
WHERE slug = 'montreal-moderne';

UPDATE shops
SET wordmark_text = 'Centerpiece',
    wordmark_style = 'title'
WHERE slug = 'le-centerpiece';

UPDATE shops
SET wordmark_text = 'maison singulier',
    wordmark_style = 'lowercase'
WHERE slug = 'maison-singulier';

UPDATE shops
SET wordmark_text = 'Yardsale Vintage',
    wordmark_style = 'title'
WHERE slug = 'yardsale-vintage';

UPDATE shops
SET wordmark_text = 'CHEZ LAMOTHE',
    wordmark_style = 'wide_caps'
WHERE slug = 'chez-lamothe';

UPDATE shops
SET wordmark_text = 'habitat',
    wordmark_style = 'lowercase'
WHERE slug = 'habitat-mobilier';

UPDATE shops
SET wordmark_text = 'Green Wall Vintage',
    wordmark_style = 'title'
WHERE slug = 'green-wall-vintage';

UPDATE shops
SET wordmark_text = 'MOSTLY DANISH',
    wordmark_style = 'wide_caps'
WHERE slug = 'mostly-danish';
